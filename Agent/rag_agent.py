
import sys

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent 

import os
from dotenv import load_dotenv
load_dotenv()
open_api_key = os.getenv("OPENAI_API_KEY")

# from pydantic import BaseModel, Field
# from typing import Optional

# class AgentResponse(BaseModel):
#     answer: str = Field(description="Final answer to the user")
#     document_name: Optional[str] = Field(default=None, description="Source document name if available")
#     document_sharepoint_url: Optional[str] = Field(default=None, description="SharePoint link of the document if available")


# -------------------------
# Tools
# -------------------------
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Tools.summary_retriever_tool import search_similar_summary
from Tools.chunk_retriever_tool import search_similar_chunk

# -------------------------
# Agent Builder Function
# -------------------------

def create_chat_agent():

    open_api_key = os.getenv("OPENAI_API_KEY")
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=open_api_key,
        temperature=0.7
    )

    # llm = llm.with_structured_output(AgentResponse)

    tools = [
        search_similar_summary,
        search_similar_chunk
    ]

    system_prompt = """
You are a helpful AI assistant.

You will receive chat_history containing the conversation between the user and assistant.

Your task:
- Understand the full conversation context.
- Focus on answering the LAST user message.

You have access to tools:

search_similar_summary
Use this when you need high level summaries of documents.

search_similar_chunk
Use this when you need detailed passages or exact information.

Rules:
- Use chat_history for context.
- Use tools when external knowledge is needed.
- Prefer summary for overview.
- Prefer chunk for precise information.
- Combine tool outputs with conversation context.

Return the final answer in JSON format:

{
  "answer": "final response",
  "document_name": "source document name if available",
  "document_sharepoint_url": "sharepoint link if available"
}

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

    print(final_text)