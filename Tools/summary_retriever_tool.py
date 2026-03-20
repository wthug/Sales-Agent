
import os
import psycopg2
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

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


def search_similar_summary( input_text: str, top_k=1) -> list:
    """Return the most similar summary to the input text based on cosine similarity."""
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

        embedding_vector = get_embeddings(input_text)
        if not embedding_vector:
            print("Failed to generate embedding vector for summary.")
            return {
                "error": "Failed to generate embeddings for the input text."
            }

        try:
            # Search Query to find similar documents based on cosine similarity
            # search_query = """
            #     SELECT document_id , summary_text , document_name , document_sharepoint_url ,1 - (summary_embedding <=> %s::vector ) AS similarity
            #     FROM all_document_summaries
            #     ORDER BY summary_embedding <=> %s::vector
            #     LIMIT %s;
            # """
            search_query = """
                SELECT document_id , summary_text , document_name , 1 - (summary_embedding <=> %s::vector ) AS similarity
                FROM all_document_summaries
                ORDER BY summary_embedding <=> %s::vector
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
            cur.close()
            conn.close()
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
    embedding_vector = get_embeddings(user_input)
    if embedding_vector:
        print("Embedding vector generated successfully!")   
    else:   
        print("Failed to generate embedding vector.")
        return
    

    result = search_similar_docs(embedding_vector,top_k=1)
    if result:
        print("Similar document found:")
        row = result[0]
        print(f"Summary ID: {row[0]}, Similarity: {row[2]}")
        print(f"Summary Text: {row[1]}")
    else:
        print("No similar documents found.")
        
     

    

if __name__ == "__main__":
    main()