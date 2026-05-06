import os
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langsmith import traceable

import psycopg2

load_dotenv()

# Extracting Variables from .env file   
open_api_key = os.getenv("OPENAI_API_KEY")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")


def get_embeddings(input_text: str) -> list:    
    try:
        embeddings = OpenAIEmbeddings(
            api_key=open_api_key,
            model="text-embedding-3-small",
            dimensions=384
        )
        return embeddings.embed_query(input_text)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return []


@traceable(run_type="retriever", name="Batch_Questions_Search")
def search_similar_batch_question(question: str, folder_name: str = None, top_k: int = 1, skip: int = 0):
    """
    Search batch_questions for rows similar to the given question using cosine similarity.
    Optionally filters by folder_name.

    Returns:
        (formatted_content: str, documents: list)
        or a dict with an 'error' key on failure.
    """
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=postgresql_password,
            host=host,
            port=port
        )
        cur = conn.cursor()
        print("Connected to PostgreSQL successfully!")

        embedding_vector = get_embeddings(question)
        if not embedding_vector:
            cur.close()
            conn.close()
            return {"error": "Failed to generate embeddings for the input question."}

        try:
            if folder_name:
                # Filter by folder_name
                search_query = """
                    SELECT
                        que_id,
                        question,
                        response,
                        row_index,
                        document_name,
                        document_sharepoint_url,
                        folder_name,
                        1 - (embeddings <=> %s::vector) AS similarity
                    FROM batch_questions
                    WHERE folder_name = %s
                      AND embeddings IS NOT NULL
                    ORDER BY embeddings <=> %s::vector
                    LIMIT %s OFFSET %s;
                """
                cur.execute(search_query, (embedding_vector, folder_name, embedding_vector, top_k, skip))
                print(f"Searching batch_questions with folder_name filter: '{folder_name}'")
            else:
                # No folder filter — search across all rows
                search_query = """
                    SELECT
                        que_id,
                        question,
                        response,
                        row_index,
                        document_name,
                        document_sharepoint_url,
                        folder_name,
                        1 - (embeddings <=> %s::vector) AS similarity
                    FROM batch_questions
                    WHERE embeddings IS NOT NULL
                    ORDER BY embeddings <=> %s::vector
                    LIMIT %s OFFSET %s;
                """
                cur.execute(search_query, (embedding_vector, embedding_vector, top_k, skip))
                print("Searching batch_questions across all folders.")

            results = cur.fetchall()
            cur.close()
            conn.close()

            if not results:
                return (
                    "No similar questions found in the batch_questions database.",
                    []
                )

            formatted_content = ""
            documents = []

            for row in results:
                que_id, q_text, response, row_index, doc_name, doc_url, fol_name, similarity = row

                formatted_content += f"""
Question: {q_text}
Response: {response}
Document: {doc_name}
Folder: {fol_name}
----------------------
"""
                documents.append({
                    "que_id": que_id,
                    "question": q_text,
                    "response": response,
                    "row_index": row_index,
                    "document_name": doc_name,
                    "document_sharepoint_url": doc_url,
                    "folder_name": fol_name,
                    "similarity": round(float(similarity), 4)
                })

            return formatted_content.strip(), documents

        except Exception as e:
            return {"error": f"Error executing search query: {e}"}

    except Exception as e:
        return {"error": f"Error connecting to PostgreSQL: {e}"}


if __name__ == "__main__":
    q = input("Enter your question: ").strip()
    fn = input("Enter folder name (AML / ALM / FM) or press Enter to skip: ").strip() or None
    result = search_similar_batch_question(q, folder_name=fn, top_k=5)
    if isinstance(result, dict):
        print("Error:", result["error"])
    else:
        content, docs = result
        print("\n=== Results ===\n")
        print(content)
