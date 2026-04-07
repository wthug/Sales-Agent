
import sys

from langchain_openai import ChatOpenAI
from typing import List, Dict, Any, Optional, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field 

import os
from dotenv import load_dotenv
load_dotenv()
open_api_key = os.getenv("OPENAI_API_KEY")

# -------------------------
# Tools
# -------------------------
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Tools.summary_retriever_tool import search_similar_summary
from Tools.chunk_retriever_tool import search_similar_chunk
from langchain_core.tools import tool
from langchain_core.documents import Document
from typing import List, Tuple

# @tool(
#     response_format="content_and_artifact",
#     description="Use this tool to retrieve relevant document summaries for a user query. Returns formatted source information for display and raw summary data for further processing"
# )
# def search_summary_tool(query:str) -> Tuple[str,List[Document]]:
#     res = search_similar_summary(query)
#     content = res.get("content", "")
#     print(content)
#     docs = res.get("artifact", [])
#     print("------Seached Summary--------")
#     print(docs)
#     formatted_parts = []
#     for i, doc in enumerate(docs):
#         # document_id , summary_text , document_name , document_sharepoint_url , similarity = doc
#         # source_info = f"[Source {i+1} ; Document Name {document_name} ; Document URL {document_sharepoint_url}]"
#         # formatted_parts.append(source_info)
#         document_id , summary_text , document_name , similarity = content
#         source_info = f"[Source {i+1} ; Document Name {document_name} ; ]"
#         formatted_parts.append(source_info)
#     formatted_context = "\n\n---\n\n".join(formatted_parts)
#     return formatted_context, docs


from langsmith import traceable

@tool(
    response_format="content_and_artifact",
    description="Retrieve relevant document summaries for a user query."
)
@traceable(run_type="tool", name="Search_Summary")
def search_summary_tool(query: str):
    content, docs = search_similar_summary(query)
    print("------ Retrieved Summary (CONTENT) ------")
    print(content)
    print("------ Retrieved Docs (ARTIFACT) ------")
    print(docs)
    # Optional: add source info for LLM clarity
    source_info_list = []
    for i, doc in enumerate(docs):
        try:
            if isinstance(doc, dict):
                document_name = doc.get("document_name", "Unknown")
                similarity = doc.get("similarity", 0),
                document_sharepoint_url=doc.get("document_sharepoint_url","")
            elif isinstance(doc, (list, tuple)) and len(doc) >= 5:
                _, _, document_name, similarity,document_sharepoint_url = doc
            else:
                continue
            source_info_list.append(
                f"[Source {i+1}: {document_name}]"
            )
        except Exception as e:
            print("Error formatting doc:", e)
    if source_info_list:
        content = content + "\n\nSources:\n" + "\n".join(source_info_list)
    return content, docs


@tool(
    response_format="content_and_artifact",
    description="Use this tool to retrieve the most relevant document chunks for a user query. You may optionally pass a doc_name to narrow the search from the database and get a more accurate response. Returns formatted source information for display and raw chunk data for further processing"
)
@traceable(run_type="tool", name="Search_Chunk")
def search_chunk_tool(query: str, doc_name: str = None) -> Tuple[str, List[Document]]:
    content, docs = search_similar_chunk(query, doc_name=doc_name)
    print("\n------ Retrieved Summary (CONTENT) ------\n")
    print(content)
    print("\n------ Retrieved Docs (ARTIFACT) ------\n")
    # print(docs)
    # Optional: add source info for LLM clarity
    source_info_list = []
    for i, doc in enumerate(docs):
        print(doc)
        print("\n")
        try:
            if isinstance(doc, dict):
                document_name = doc.get("document_name", "Unknown")
                similarity = doc.get("similarity", 0)
                document_sharepoint_url=doc.get("document_sharepoint_url","")
            elif isinstance(doc, (list, tuple)) and len(doc) >= 5:
                _, _, document_name, similarity,document_sharepoint_url = doc
            else:
                continue
            source_info_list.append(
                f"[Source {i+1}: {document_name}]"
            )
        except Exception as e:
            print("Error formatting doc:", e)
    if source_info_list:
        content = content + "\n\nSources:\n" + "\n".join(source_info_list)
    return content, docs



# -------------------------
# Agent Builder Function (LangGraph)
# -------------------------

class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    current_query: str
    target_document: str
    summary_query: str
    summary_iterations: int
    chunk_query: str
    responses: List[str]
    chunk_iterations: int
    current_action: str

class AnalyzeQueryOutput(BaseModel):
    user_query: str = Field(description="The core user question to answer.")
    action: str = Field(description="Must be 'summary', 'chunk', or 'answer'. 'summary' to search summaries, 'chunk' to search chunks directly.")
    tool_query: str = Field(description="The search query for the chosen tool.")
    target_document: str = Field(description="If action is 'chunk', the document name if known.")

class EvaluateSummaryOutput(BaseModel):
    action: str = Field(description="Decision on next step. Must be 'answer', 'chunk', or 'retry_summary'.")
    target_document: str = Field(description="The name of the document identified from the summary, if any.")
    chunk_query: str = Field(description="If action is 'chunk', the query to search matching chunks.")
    new_summary_query: str = Field(description="If action is 'retry_summary', the new summary query.")

class EvaluateChunksOutput(BaseModel):
    action: str = Field(description="Decision on next step. Must be 'answer' or 'retry_chunk'.")
    useful_chunks: List[str] = Field(description="Facts extracted from chunks relevant to the user query.")
    new_chunk_query: str = Field(description="If action is 'retry_chunk', the new query. Max two retries.")

def get_llm():
    open_api_key = os.getenv("OPENAI_API_KEY")
    return ChatOpenAI(model="gpt-4o-mini", api_key=open_api_key, temperature=0.0)

def analyze_query_node(state: GraphState):
    llm = get_llm().with_structured_output(AnalyzeQueryOutput)
    msgs = state.get("messages", [])
    history = "\n".join([f"{getattr(m, 'type', 'unknown')}: {getattr(m, 'content', '')}" for m in msgs])
    prompt = f"""
Chat History:
{history}

What is the user's latest actual query? 
If you need general context or don't know the specific document, set action='summary' and create a summary_query. 
If you know the expected document and need precise details, set action='chunk', the chunk_query, and target_document. 
If no tool is needed at all, action='answer'.
"""
    res = llm.invoke(prompt)
    
    return {
        "current_query": res.user_query,
        "current_action": res.action,
        "summary_query": res.tool_query if res.action == 'summary' else "",
        "chunk_query": res.tool_query if res.action == 'chunk' else "",
        "target_document": res.target_document or ""
    }

def retrieve_summary_node(state: GraphState):
    query = state.get("summary_query", state.get("current_query", ""))
    content, docs = search_similar_summary(query)
    
    class CustomToolMessage(ToolMessage):
        artifact: Any = None
    
    tool_msg = CustomToolMessage(content=content, artifact=docs, tool_call_id="summary_search_" + str(state.get("summary_iterations",0)), name="search_summary_tool")
    
    return {
        "messages": [tool_msg],
        "summary_iterations": state.get("summary_iterations", 0) + 1
    }

def evaluate_summary_node(state: GraphState):
    llm = get_llm().with_structured_output(EvaluateSummaryOutput)
    
    last_msg_content = state["messages"][-1].content
    prompt = f"""
Query: {state.get('current_query', '')}
Retrieved Summary: {last_msg_content}

You must decide the next step based on the provided summary:
1. If the exact answer is present in the summary, set action='answer'.
2. If you know the right document but need specific text details, set action='chunk' and provide the target_document and a chunk_query.
3. If this summary is useless and we should search summaries again with a different query, set action='retry_summary' and a new_summary_query. (Max 2 retries)
"""
    res = llm.invoke(prompt)
    
    action = res.action
    iters = state.get("summary_iterations", 0)
    if action == "retry_summary" and iters >= 2:
        action = "answer"
    
    return {
        "current_action": action,
        "chunk_query": res.chunk_query or "",
        "target_document": res.target_document or state.get("target_document", ""),
        "summary_query": res.new_summary_query or ""
    }

def retrieve_chunks_node(state: GraphState):
    query = state.get("chunk_query", state.get("current_query", ""))
    doc_name = state.get("target_document", None)
    content, docs = search_similar_chunk(query, doc_name=doc_name)
    
    class CustomToolMessage(ToolMessage):
        artifact: Any = None
        
    tool_msg = CustomToolMessage(content=content, artifact=docs, tool_call_id="chunk_search_" + str(state.get("chunk_iterations",0)), name="search_chunk_tool")
    
    return {
        "messages": [tool_msg],
        "chunk_iterations": state.get("chunk_iterations", 0) + 1
    }

def evaluate_chunks_node(state: GraphState):
    llm = get_llm().with_structured_output(EvaluateChunksOutput)
    
    last_msg_content = state["messages"][-1].content
    prompt = f"""
Original Query: {state.get('current_query', '')}
Retrieved Chunks: {last_msg_content}

Extract any specific facts from the chunks that help answer the query into 'useful_chunks'.
If we need to search chunks again for a different term to complete the answer, action='retry_chunk' and provide new_chunk_query. Else action='answer'. (Max 2 retries).
"""
    res = llm.invoke(prompt)
    
    action = res.action
    iters = state.get("chunk_iterations", 0)
    if action == "retry_chunk" and iters >= 2:
        action = "answer"
        
    responses = state.get("responses", []) + res.useful_chunks
    
    return {
        "current_action": action,
        "responses": responses,
        "chunk_query": res.new_chunk_query or ""
    }

def generate_answer_node(state: GraphState):
    llm = get_llm()
    query = state.get('current_query', '')
    responses = "\\n".join(state.get("responses", []))
    last_msg = state['messages'][-1].content if state['messages'] else ""
    
    system_prompt = f"""
You are an intelligent Sales Agent assistant designed to answer user queries using proposal documents.
Your primary goal is to accurately answer the LAST user query using the available tool responses.

Query to answer: {query}

Accumulated Exact Facts from Chunks: 
{responses}

Most recent Tool output:
{last_msg}

Rules: Keep it professional, highly concise. Use only the context provided above.
"""
    answer_msg = AIMessage(content=llm.invoke(system_prompt).content)
    return {"messages": [answer_msg]}

def route_initial(state: GraphState):
    action = state.get("current_action", "answer")
    if action == "summary": return "retrieve_summary"
    if action == "chunk": return "retrieve_chunks"
    return "generate_answer"

def route_evaluate_summary(state: GraphState):
    action = state.get("current_action", "answer")
    if action == "retry_summary": return "retrieve_summary"
    if action == "chunk": return "retrieve_chunks"
    return "generate_answer"

def route_evaluate_chunks(state: GraphState):
    action = state.get("current_action", "answer")
    if action == "retry_chunk": return "retrieve_chunks"
    return "generate_answer"

def create_chat_agent():
    workflow = StateGraph(GraphState)
    
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("retrieve_summary", retrieve_summary_node)
    workflow.add_node("evaluate_summary", evaluate_summary_node)
    workflow.add_node("retrieve_chunks", retrieve_chunks_node)
    workflow.add_node("evaluate_chunks", evaluate_chunks_node)
    workflow.add_node("generate_answer", generate_answer_node)
    
    workflow.set_entry_point("analyze_query")
    
    workflow.add_conditional_edges("analyze_query", route_initial, ["retrieve_summary", "retrieve_chunks", "generate_answer"])
    
    workflow.add_edge("retrieve_summary", "evaluate_summary")
    workflow.add_conditional_edges("evaluate_summary", route_evaluate_summary, ["retrieve_summary", "retrieve_chunks", "generate_answer"])
    
    workflow.add_edge("retrieve_chunks", "evaluate_chunks")
    workflow.add_conditional_edges("evaluate_chunks", route_evaluate_chunks, ["retrieve_chunks", "generate_answer"])
    
    workflow.add_edge("generate_answer", END)
    
    return workflow.compile()


if __name__ == "__main__": 
    # Example chat history
    chat_history = [
        {"role": "user", "content": "Tell me about ALM"}
    ]
    agent = create_chat_agent()
    response = agent.invoke({
        "messages": chat_history
    })
    final_text = response["messages"][-1].content
    
    result = {
        "output" : final_text
    }

    docs: List[Document] = []

    for msg in reversed(response["messages"]):
        if msg.type == "tool" and hasattr(msg, "artifact"):
            docs = (msg.artifact)
            break
        
    if len(docs)>0:
        doc_entry = docs[0]
        if isinstance(doc_entry, dict):
            doc_name = doc_entry.get("document_name", "")
            doc_sharepoint_url = doc_entry.get("document_sharepoint_url", "")
            page_num = doc_entry.get("page_number", "")
            result["page_number"] = page_num
        elif len(doc_entry) == 5:
            id,doc_text,doc_name,doc_sharepoint_url,score = doc_entry
        elif len(doc_entry) == 4:
            id,doc_text,doc_name,score = doc_entry
            doc_sharepoint_url = ""
        else:
            doc_name = ""
            doc_sharepoint_url = ""
            
        result["document_name"] = doc_name
        result["document_sharepoint_url"] = doc_sharepoint_url
    print("-------")
    print(result)
    # print(final_text)