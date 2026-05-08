import os
import sys
import json
from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
open_api_key = os.getenv("OPENAI_API_KEY")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from psycopg2.extras import Json

from sql_script import Database

# ---------------------------------------------------------
# Pydantic Schemas for Structured Output
# ---------------------------------------------------------

class CategoryAssignment(BaseModel):
    category_name: str = Field(description="Name of the category (either existing or a newly proposed one)")
    description: str = Field(description="Description of the category. Required if this is a new category, otherwise empty string")
    is_new: bool = Field(description="Set to true if this is a newly generated category, false if it's from the existing_categories list")

class ClassificationOutput(BaseModel):
    assigned_categories: List[CategoryAssignment] = Field(description="List of categories this question falls into")

class SingleCategoryOutput(BaseModel):
    category_name: str = Field(description="Name of the existing category that best matches the query")

# ---------------------------------------------------------
# LangGraph State Definitions
# ---------------------------------------------------------

class IngestionState(TypedDict):
    question: str
    response: str
    document_name: str
    row_index: int
    folder_name: str
    existing_categories: List[Dict[str, str]]
    assigned_categories: List[CategoryAssignment]

class QueryState(TypedDict):
    question: str
    folder_name: str
    existing_categories: List[Dict[str, str]]
    assigned_category: str
    context_data: List[Dict[str, Any]]
    final_answer: str

# ---------------------------------------------------------
# Ingestion Nodes
# ---------------------------------------------------------

def classify_ingestion_node(state: IngestionState) -> IngestionState:
    llm = ChatOpenAI(
        model="gpt-5-mini", 
        api_key=open_api_key,
        temperature=0.0
    ).with_structured_output(ClassificationOutput)

    sys_prompt = f"""You are an expert taxonomist and data categorizer for {state['folder_name']} domain.
Your task is to analyze a given Question and Response, and classify it into one or more categories.

Existing Categories for {state['folder_name']}:
{json.dumps(state['existing_categories'], indent=2)}

Instructions:
1. If the question/response strongly fits into existing categories, assign those.
2. If it spans multiple topics, assign it to multiple categories.
3. If it does not fit any existing category, generate a NEW category (or multiple new ones) that accurately describes the topic. Provide a clear description for any new category.
4. For any existing category you choose, set is_new to false. For any newly generated category, set is_new to true.
"""

    user_prompt = f"Question: {state['question']}\n\nResponse: {state['response']}"

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=user_prompt)
    ]

    output: ClassificationOutput = llm.invoke(messages)
    
    state["assigned_categories"] = output.assigned_categories
    return state


def update_db_node(state: IngestionState) -> IngestionState:
    conn = Database.get_connection()
    if not conn:
        print("[Error] Failed to connect to DB in update_db_node")
        return state

    try:
        with conn.cursor() as cur:
            q_obj = {
                "question": state["question"],
                "response": state["response"],
                "document_name": state["document_name"],
                "row_index": state["row_index"]
            }

            for assignment in state["assigned_categories"]:
                cat_name = assignment.category_name
                desc = assignment.description
                is_new = assignment.is_new

                cur.execute("""
                    INSERT INTO batch_categories (folder_name, cat_name, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (folder_name, cat_name) DO NOTHING;
                """, (state["folder_name"], cat_name, desc))

                cur.execute("""
                    UPDATE batch_categories 
                    SET context = context || %s::jsonb 
                    WHERE folder_name = %s AND cat_name = %s;
                """, (Json([q_obj]), state["folder_name"], cat_name))

        conn.commit()
    except Exception as e:
        print(f"[Error] DB update failed: {e}")
        conn.rollback()
    finally:
        Database.put_connection(conn)

    return state

# ---------------------------------------------------------
# Query Nodes
# ---------------------------------------------------------

def classify_query_node(state: QueryState) -> QueryState:
    llm = ChatOpenAI(
        model="gpt-5-mini", 
        api_key=open_api_key,
        temperature=0.0
    ).with_structured_output(SingleCategoryOutput)
    
    sys_prompt = f"""You are an expert taxonomist. Based on the user's question, determine the single most relevant category from the existing categories for the domain '{state['folder_name']}'.
    
Existing Categories:
{json.dumps(state['existing_categories'], indent=2)}

If none are a perfect fit, pick the closest one."""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=state['question'])
    ]
    
    output: SingleCategoryOutput = llm.invoke(messages)
    state["assigned_category"] = output.category_name
    return state

def fetch_context_node(state: QueryState) -> QueryState:
    conn = Database.get_connection()
    context_data = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT context FROM batch_categories 
                    WHERE folder_name = %s AND cat_name = %s
                """, (state['folder_name'], state['assigned_category']))
                row = cur.fetchone()
                if row and row[0]:
                    context_data = row[0]
        except Exception as e:
            print(f"[Error] fetching context: {e}")
        finally:
            Database.put_connection(conn)
    
    state["context_data"] = context_data
    return state

def generate_answer_node(state: QueryState) -> QueryState:
    llm = ChatOpenAI(
        model="gpt-5-mini", 
        api_key=open_api_key,
        temperature=0.0
    )
    
    sys_prompt = f"""You are a Senior Solutions Consultant. Use the following context to answer the user's question. 
The context consists of past questions and their validated responses from the '{state['assigned_category']}' category.

Context:
{json.dumps(state['context_data'], indent=2)}

Answer the user's question based ONLY on the provided context. If the context does not contain relevant information, state that clearly.

### RESPONSE FORMAT (STRICT)

Line 1:
- Yes / No / Fully Aligned / Needs Modification / Not Aligned

Then follow with a structured response:
1. Answer the question about availability of the feature.
2. Explain a bit about how we handle this requirement.
3. Include parts of the value proposition it will bring to the client based on the approach we follow (this is the part which attracts the customer and makes the answer impressive).
4. Conclude with a clear summary."""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=state['question'])
    ]
    
    output = llm.invoke(messages)
    state["final_answer"] = output.content
    return state


# ---------------------------------------------------------
# Class Wrapper
# ---------------------------------------------------------

class CategoryGraph:
    def __init__(self):
        self.categories = self._preload_categories()
        self.ingestion_graph = self._build_ingestion_graph()
        self.query_graph = self._build_query_graph()
        print("[OK] CategoryGraph initialized and categories preloaded")

    def _preload_categories(self) -> Dict[str, List[Dict[str, str]]]:
        conn = Database.get_connection()
        if not conn:
            return {}
        
        cats = {}
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT folder_name, cat_name, description FROM batch_categories")
                for row in cur.fetchall():
                    folder = row[0]
                    if folder not in cats:
                        cats[folder] = []
                    cats[folder].append({
                        "cat_name": row[1],
                        "description": row[2]
                    })
        except Exception as e:
            print(f"Error preloading categories: {e}")
        finally:
            Database.put_connection(conn)
        
        return cats

    def _build_ingestion_graph(self):
        builder = StateGraph(IngestionState)
        builder.add_node("classify", classify_ingestion_node)
        builder.add_node("update_db", update_db_node)

        builder.add_edge(START, "classify")
        builder.add_edge("classify", "update_db")
        builder.add_edge("update_db", END)

        return builder.compile()

    def _build_query_graph(self):
        builder = StateGraph(QueryState)
        builder.add_node("classify", classify_query_node)
        builder.add_node("fetch", fetch_context_node)
        builder.add_node("generate", generate_answer_node)

        builder.add_edge(START, "classify")
        builder.add_edge("classify", "fetch")
        builder.add_edge("fetch", "generate")
        builder.add_edge("generate", END)

        return builder.compile()

    def process_ingestion_row(self, folder_name: str, question: str, response: str, document_name: str, row_index: int):
        folder_cats = self.categories.get(folder_name, [])
        initial_state: IngestionState = {
            "question": question,
            "response": response,
            "document_name": document_name,
            "row_index": row_index,
            "folder_name": folder_name,
            "existing_categories": folder_cats,
            "assigned_categories": []
        }

        result = self.ingestion_graph.invoke(initial_state)

        for assignment in result.get("assigned_categories", []):
            if assignment.is_new:
                if folder_name not in self.categories:
                    self.categories[folder_name] = []
                if not any(c["cat_name"] == assignment.category_name for c in self.categories[folder_name]):
                    self.categories[folder_name].append({
                        "cat_name": assignment.category_name,
                        "description": assignment.description
                    })
                    print(f"[*] Added new category '{assignment.category_name}' to memory for {folder_name}")
        
        return result

    def process_query_row(self, folder_name: str, question: str):
        folder_cats = self.categories.get(folder_name, [])
        if not folder_cats:
            return "No categories available for this domain."

        initial_state: QueryState = {
            "question": question,
            "folder_name": folder_name,
            "existing_categories": folder_cats,
            "assigned_category": "",
            "context_data": [],
            "final_answer": ""
        }
        
        result = self.query_graph.invoke(initial_state)
        return result.get("final_answer", "Failed to generate answer.")
