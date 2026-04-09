
import sys

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent 
from pgvector.psycopg2 import register_vector
import psycopg2

import os
from dotenv import load_dotenv
load_dotenv()
open_api_key = os.getenv("OPENAI_API_KEY")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")

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
    description="Retrieve relevant document summaries for a user query. You MUST pass the msg_id."
)
@traceable(run_type="tool", name="Search_Summary")
def search_summary_tool(query: str, msg_id: int = None):
    if msg_id:
        print("msg_id passed in summary search tool" , msg_id)
    content , metadata = search_similar_summary(query)
    print("------ Retrieved Summary (CONTENT) ------")
    # print(content)

    print("metadata:\n ", metadata)

    try:
        import json
        conn2 = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=postgresql_password,
            host=host,
            port=port
        )
        cur2 = conn2.cursor()
        cur2.execute("UPDATE messages SET sources = COALESCE(sources, '[]'::jsonb) || %s::jsonb WHERE message_id = %s", (json.dumps(metadata), msg_id))
        conn2.commit()
        cur2.close()
        conn2.close()
        print("Updated messages with sources of summaries")

    except Exception as e:
        import traceback
        print("Error updating messages table with sources in summary DB:")
        traceback.print_exc()

    return content


@tool(
    description="Use this tool to retrieve the most relevant document chunks for a user query. You may optionally pass a doc_name to narrow the search from the database and get a more accurate response. You MUST pass the msg_id."
)
@traceable(run_type="tool", name="Search_Chunk")
def search_chunk_tool(query: str, msg_id: int, doc_name: str = None) -> str:

    if msg_id:
        print("msg_id passed in chunk search tool",msg_id)

    content , metadata = search_similar_chunk(query, doc_name=doc_name)
    print("\n------ Retrieved Chunks (CONTENT) ------\n")
    # print(content)
    print("Metadata :\n",metadata)

    try:
        import json
        conn2 = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=postgresql_password,
            host=host,
            port=port
        )
        cur2 = conn2.cursor()
        cur2.execute("UPDATE messages SET sources = COALESCE(sources, '[]'::jsonb) || %s::jsonb WHERE message_id = %s", (json.dumps(metadata), msg_id))
        conn2.commit()
        cur2.close()
        conn2.close()
        print("Updated messages with sources of chunks")
    except Exception as e:
        import traceback
        print("Error updating messages table with sources in chunk DB:")
        traceback.print_exc()

    return content



# -------------------------
# Agent Builder Function
# -------------------------

def create_chat_agent():

    open_api_key = os.getenv("OPENAI_API_KEY")
    
    llm = ChatOpenAI(
        model="gpt-5-mini",
        api_key=open_api_key,
        temperature=0.0
    )

    # llm = llm.with_structured_output(AgentResponse)

    tools = [
        search_summary_tool,
        search_chunk_tool
    ]

    system_prompt = """
You are an intelligent Sales Agent assistant designed to answer user queries using proposal documents.

You will receive chat_history containing the full conversation and message_id where your final response to query will be saved.
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
- You may pass an optional 'doc_name' argument to narrow the search from the DB and get a more accurate response.
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
- Do not forget to pass message_id to tools as well to save the sources
- Focus on relevant sections only

Step 4: Generate final answer
- Combine retrieved information
- Ensure accuracy and completeness

----------------------------------------
 IMPORTANT RULES
----------------------------------------

- Query-Lock Precision: Provide only the specific information requested. If a retrieved chunk contains extra data, filter it out and deliver only the direct answer.
- Brevity by Default: If asked for a "brief" summary, limit the response to 2–3 punchy sentences or high-level bullet points.
- Zero-Extrapolation: Do not provide "helpful" context, background, or related details unless explicitly triggered by the prompt.
- NEVER Hallucinate: If information is missing from the tool outputs, clearly state that the information is not found.
- Source Integrity: Always rely on tool outputs. Never assume or guess missing information.
- Professional Tone: Maintain a concise, sales-oriented, and "bottom-line" professional tone.
- No Meta-Talk: Do not expose tool names, search processes, or internal reasoning.

----------------------------------------
 COMMON MISTAKES TO AVOID
----------------------------------------

- Information Bloat: Giving extra information that wasn't asked for just because it was in the retrieved data.
- Vague Summarization: Failing to provide a short, precise answer when a "brief" response is requested.
- Tool Misuse: Using the summary tool for detailed, granular answers or skipping it when the query is broad.
- Context Mixing: Blending unrelated documents or "filling in the gaps" with information not present in the search results.
- Ignoring Constraints: Failing to filter retrieved chunks to extract only the required, query-related info.

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