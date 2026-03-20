
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

@tool(
    response_format="content_and_artifact",
    description="Use this tool to retrieve relevant document summaries for a user query. Returns formatted source information for display and raw summary data for further processing"
)
def search_summary_tool(query:str) -> Tuple[str,List[Document]]:
    
    res = search_similar_summary(query)

    docs = res["output"]

    print("------Seached Summary--------")
    print(docs)

    formatted_parts = []

    for i, doc in enumerate(docs):
        
        # document_id , summary_text , document_name , document_sharepoint_url , similarity = doc
        # source_info = f"[Source {i+1} ; Document Name {document_name} ; Document URL {document_sharepoint_url}]"
        # formatted_parts.append(source_info)
        document_id , summary_text , document_name , similarity = doc
        source_info = f"[Source {i+1} ; Document Name {document_name} ; ]"
        formatted_parts.append(source_info)

    formatted_context = "\n\n---\n\n".join(formatted_parts)
 
    return formatted_context, docs


@tool(
    response_format="content_and_artifact",
    description="Use this tool to retrieve the most relevant document chunks for a user query. Returns formatted source information for display and raw chunk data for further processing"
)
def search_chunk_tool(query:str) -> Tuple[str,List[Document]]:
    res = search_similar_chunk(query)

    docs = res["output"]

    print("------Seached chunks--------")
    print(docs)


    formatted_parts = []

    for i, doc in enumerate(docs):
    
        # document_id , chunk_text , document_name , document_sharepoint_url , similarity = doc
        # source_info = f"[Source {i+1} ; Document Name {document_name} ; Document URL {document_sharepoint_url}]"
        # formatted_parts.append(source_info)
        document_id , chunk_text , document_name  , similarity = doc
        source_info = f"[Source {i+1} ; Document Name {document_name} ;]"
        formatted_parts.append(source_info)

    formatted_context = "\n\n---\n\n".join(formatted_parts)
 
    return formatted_context, docs



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

    system_prompt = """
You are a helpful AI assistant.

You will receive chat_history containing the conversation between the user and assistant.

Your task:
- Understand the full conversation context.
- Focus on answering the LAST user message.

You have access to tools:

search_summary_tool
- Use this when you need high level summaries of documents.
- You may call this tool atmost 3 times

search_similar_chunk
- Use this when you need detailed passages or exact information.
- You may call this tool atmost 3 times

Rules:
- Use chat_history for context.
- Use tools when external knowledge is needed.
- Prefer summary for overview.
- Prefer chunk for precise information.
- Combine tool outputs with conversation context.
- Return final answer as a string 

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