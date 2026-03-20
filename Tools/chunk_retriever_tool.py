
import os
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings

import psycopg2


load_dotenv()

# Extracting Variables from .env file   
open_api_key = os.getenv("OPENAI_API_KEY")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")


# To generate embeddings

def get_embeddings(input_text: str) -> list:
    
    try:
        embeddings = OpenAIEmbeddings(
            api_key=open_api_key,
            model="text-embedding-3-small",
            dimensions=384
        )
        embedding_vector = embeddings.embed_query(input_text)
        return embedding_vector
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return []
   

def search_similar_chunk(user_input :str, top_k=5) -> list:
    """Return the most similar chunks to the user input based on cosine similarity."""
    try:
        # Connection Configuration
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=postgresql_password,
            host=host,
            port=port
        )
        cur = conn.cursor()
        print("Connected to PostgreSQL successfully!")

        embedding_vector = get_embeddings(user_input)
        if not embedding_vector:
            print("Failed to generate embedding vector for chunk.")
            return {
                "error": "Failed to generate embeddings for the input text."
            }

        try:
            # Search Query
            # search_query = """
            #     SELECT document_id , chunk_text ,document_name, document_sharepoint_url ,1 - (embedding <=> %s::vector ) AS similarity
            #     FROM all_document_chunks
            #     ORDER BY embedding <=> %s::vector
            #     LIMIT %s;
            # """
            search_query = """
                SELECT document_id , chunk_text ,document_name, 1 - (embedding <=> %s::vector ) AS similarity
                FROM all_document_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            
            cur.execute(search_query, (embedding_vector , embedding_vector , top_k))
            results = cur.fetchall()

            cur.close()
            conn.close()
            
            return {
                "output": results
            }
        
        except Exception as e:
            return {
                "error" : f"Error executing search query: {e}"
            }
    
    except Exception as e:
        return {
            "error" : f"Error connecting to PostgreSQL: {e}"
        }
    

def main():
    user_input = input("Enter your query: ")

    # Generating embeddings for the user input
    result = search_similar_chunk(user_input, top_k=1)
    if result["output"]:
        print(result["output"][0])
    else:
        print("No results found.")


if __name__ == "__main__":
    main()  

