# Agent/agent.py

import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
import sys

# Ensure root folder is in import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Correct import path
from Tools.summary_retriever_tool import get_embeddings, search_similar_docs    
from Tools.chunk_retriever_tool import search_similar_docs_chunk
from dotenv import load_dotenv

import langchain

langchain.debug = False


load_dotenv()

open_api_key = os.getenv("OPENAI_API_KEY")

def create_chatbot_agent(claim_record):
    llm = ChatOpenAI(
        model="gpt-5",
        temperature=0,
        api_key=open_api_key
    )

    tools = [search_similar_docs_chunk , search_similar_docs]
    
    prompt = f"""
    You are an AI assistant specialized in handling insurance claims by retrieving relevant policy information.
    Do not answer any question which is out of scope of insurance claims handling and guide them to ask question related to insurance claims only.
    This is the claim submitted by the user:
    {claim_record}
    """
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=prompt
    )

    return agent
