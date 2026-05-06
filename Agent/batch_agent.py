import os
import sys
from dotenv import load_dotenv

load_dotenv()
open_api_key = os.getenv("OPENAI_API_KEY")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import tool
from langsmith import traceable

from Tools.batch_questions_retriever_tool import search_similar_batch_question


# -------------------------
# Tool
# -------------------------

@tool(
    description=(
        "Search the batch_questions database for rows that are semantically similar to the given question. "
        "You MUST pass all five arguments: 'question', 'folder_name', 'file_name', 'index', and 'skip'. "
        "Pass 'question' as the user's query. "
        "Pass 'folder_name', 'file_name', 'index', and 'skip' exactly as provided in your context. "
    )
)
@traceable(run_type="tool", name="Search_Batch_Questions")
def search_batch_questions_tool(question: str, folder_name: str, file_name: str, index: int, skip: int = 0) -> str:
    """Retrieve similar past questions and their responses from the batch_questions table."""
    print(f"\n------ Batch Questions Search ------")
    print(f"Question: {question[:80]}...")
    print(f"Folder filter: {folder_name}")
    print(f"File name: {file_name}")
    print(f"Index: {index}")
    print(f"Skip: {skip}")
    print(f"------ Batch Questions Search End ------\n\n")

    content, documents = search_similar_batch_question(question, folder_name=folder_name, skip=skip)

    if documents:
        from psycopg2.extras import Json
        from sql_script import Database
        try:
            conn = Database.get_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO metadata (file_name, index, skip, metadata) VALUES (%s, %s, %s, %s)",
                        (file_name, index, skip, Json(documents))
                    )
                conn.commit()
                Database.put_connection(conn)
        except Exception as e:
            print(f"Error inserting into metadata table: {e}")

    if not documents:
        return "No similar documents found."

    return content



# -------------------------
# Agent Builder
# -------------------------

def create_batch_agent():

    llm = ChatOpenAI(
        model="gpt-5-mini",
        api_key=open_api_key,
        temperature=0.0
    )

    tools = [search_batch_questions_tool]

    system_prompt = """
You are a Senior Solutions Consultant for SAS, supporting multiple domains such as AML, ALM, Fraud Management (FM), and related solutions.
Your task is to assess whether the SAS solution meets the client’s requirement based strictly on previously evaluated batch data.

### INPUT YOU WILL RECEIVE

Each user message contains:
- The user query (Item + Specification context)
- A [CONTEXT: ...] block at the end with: folder_name, file_name, index, and skip

Example:
  Item: AML Transaction Monitoring
  Specification: Real-time alerts

  [CONTEXT: folder_name=AML, file_name=output_batch.xlsx, index=3, skip=0]

You MUST extract folder_name, file_name, index, and skip from the [CONTEXT: ...] block.

### AVAILABLE TOOL

You have access to a retrieval tool "search_batch_questions_tool" that returns relevant past assessments across domains.

### MANDATORY WORKFLOW

For every request:
1. Extract the user query (everything before the [CONTEXT: ...] block)
2. Extract folder_name, file_name, index, and skip from the [CONTEXT: ...] block
3. Call the retrieval tool with ALL five parameters:
    - question → the user query text (before [CONTEXT:])
    - folder_name → extracted folder_name (use None if it says None)
    - file_name → extracted file_name
    - index → extracted index (as an integer)
    - skip → extracted skip (as an integer)
    - Do not skip any parameter.
4. Analyze retrieved results
    - Use only the returned data
    - Interpret alignment within the given domain context (folder_name)
5. Generate final response
    - Do not mention the tool or the [CONTEXT: ...] block
    - Do not include internal reasoning
    - Do not use external knowledge

### RESPONSE FORMAT (STRICT)

Line 1:
- Yes / No / Fully Aligned / Needs Modification / Not Aligned

Then follow with a structured response:
1. Answer the question about availability of the feature.
2. Explain a bit about how we handle this requirement.
3. Include parts of the value proposition it will bring to the client based on the approach we follow (this is the part which attracts the customer and makes the answer impressive).
4. Conclude with a clear summary.

### FAILURE CONDITION

If no relevant data is retrieved:
- Not Aligned
- The available information does not fully address this requirement.

### IMPORTANT RULES

- You must call the retrieval tool before answering.
- You must pass all inputs exactly as received.
- You must not hallucinate or infer beyond retrieved data.
- You must not expose tool usage or internal steps.
- Keep tone concise, confident, and client-ready.
"""
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )

    return agent


if __name__ == "__main__":
    agent = create_batch_agent()
    q = input("Enter question (Item + Specification): ").strip()
    fn = input("Folder name (AML/ALM/FM or Enter to skip): ").strip() or None
    augmented = f"{q}\n\n[CONTEXT: folder_name={fn}, file_name=test_file.xlsx, index=0]"
    response = agent.invoke({
        "messages": [{"role": "user", "content": augmented}],
    })
    print("\n=== Agent Response ===")
    print(response["messages"][-1].content)