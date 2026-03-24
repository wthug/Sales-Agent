
import sys

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent 

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

@tool(
    response_format="content_and_artifact",
    description="Retrieve relevant document summaries for a user query."
)
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
                similarity = doc.get("similarity", 0)
            elif isinstance(doc, (list, tuple)) and len(doc) >= 4:
                _, _, document_name, similarity = doc
            else:
                continue
            source_info_list.append(
                f"[Source {i+1}: {document_name} | relevance: {similarity:.2f}]"
            )
        except Exception as e:
            print("Error formatting doc:", e)
    if source_info_list:
        content = content + "\n\nSources:\n" + "\n".join(source_info_list)
    return content, docs


@tool(
    response_format="content_and_artifact",
    description="Use this tool to retrieve the most relevant document chunks for a user query. Returns formatted source information for display and raw chunk data for further processing"
)
def search_chunk_tool(query:str) -> Tuple[str,List[Document]]:
    content, docs = search_similar_chunk(query)
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
                similarity = doc.get("similarity", 0)
            elif isinstance(doc, (list, tuple)) and len(doc) >= 4:
                _, _, document_name, similarity = doc
            else:
                continue
            source_info_list.append(
                f"[Source {i+1}: {document_name} | relevance: {similarity:.2f}]"
            )
        except Exception as e:
            print("Error formatting doc:", e)
    if source_info_list:
        content = content + "\n\nSources:\n" + "\n".join(source_info_list)
    return content, docs



# -------------------------
# Agent Builder Function
# -------------------------

def create_chat_agent():

    open_api_key = os.getenv("OPENAI_API_KEY")
    
    llm = ChatOpenAI(
        model="gpt-5-mini",
        api_key=open_api_key,
        temperature=0.7
    )

    # llm = llm.with_structured_output(AgentResponse)

    tools = [
        search_summary_tool,
        search_chunk_tool
    ]

    system_prompt =system_prompt = system_prompt = system_prompt = """
You are an intelligent Sales Agent assistant designed to answer user queries using proposal documents.

You will receive chat_history containing the full conversation.
Your primary goal is to accurately answer the LAST user query using the available tools.

----------------------------------------
 CORE RESPONSIBILITIES
----------------------------------------
1. Understand the user’s intent from the latest query
2. Use chat history for additional context if needed
3. Identify the most relevant document(s)
4. Retrieve precise and relevant information
5. Provide a clear, accurate, and business-relevant response

----------------------------------------
 AVAILABLE TOOLS
----------------------------------------

1. search_summary_tool
- Use this to identify the most relevant document(s)
- Provides high-level summaries of documents
- Helps when:
  • Query is vague or broad
  • No document is explicitly mentioned
- Maximum 2 calls

2. search_chunk_tool
- Use this to retrieve detailed and specific information from documents
- Helps when:
  • You need exact details (pricing, scope, deliverables, timelines, etc.)
  • You already know which document is relevant
- Maximum 2 calls

----------------------------------------
 DECISION LOGIC (VERY IMPORTANT)
----------------------------------------

Step 1: Understand the query
- If query is vague or document is unknown → use search_summary_tool
- If query is specific → you may directly use search_chunk_tool

Step 2: Identify document
- Use summary tool to select the most relevant document
- DO NOT rely on assumptions

Step 3: Retrieve details
- Use search_chunk_tool to fetch precise information from the selected document
- Focus on relevant sections only

Step 4: Generate final answer
- Combine retrieved information
- Ensure accuracy and completeness

----------------------------------------
 IMPORTANT RULES
----------------------------------------

- NEVER hallucinate or assume missing information
- ALWAYS rely on tool outputs
- If information is not found → clearly say so
- DO NOT expose tool names or internal reasoning
- Prefer concise but complete answers
- Maintain a professional, sales-oriented tone

----------------------------------------
 COMMON MISTAKES TO AVOID
----------------------------------------

- Using summary tool for detailed answers 
- Skipping summary when query is vague 
- Not using chunk tool for specific queries 
- Mixing unrelated documents 
- Guessing missing information 

----------------------------------------
OUTPUT FORMAT
----------------------------------------

- Provide a clear, structured answer
- Include relevant business details (scope, pricing, deliverables, etc.)
- Keep response concise and informative

"""


    agent = create_agent(
        model=llm, 
        tools=tools, 
        system_prompt=system_prompt
    )

    return agent


if __name__ == "__main__": 
    # Example chat history
    chat_history = [
        {"role": "user", "content": "Facility Risk Profile Creation"}
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
        id,doc_text,doc_name,doc_sharepoint_url,score = docs[0]
        result["document_name"] = doc_name
        result["document_sharepoint_url"] = doc_sharepoint_url 
    print("-------")
    print(result)
    # print(final_text)