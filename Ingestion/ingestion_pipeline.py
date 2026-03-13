from langchain_community.document_loaders import DirectoryLoader, TextLoader ,PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate

from pgvector.psycopg2 import register_vector
import psycopg2
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Extracting Variables from .env file
open_api_key = os.getenv("open_ai_key")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")





def generate_summary(input_text: str) -> str:
    try:
        llm = OpenAI(
            api_key=open_api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            Read the following text carefully. 
            Generate a comprehensive summary of approximately 300 words that captures all key points and essential details.

            Input Text:
            {text}

            Return the summary as a single, coherent paragraph that effectively conveys the main ideas and important information from the input text.
            """
        )
        chain = prompt | llm
        summary = chain.invoke({"text": input_text})
        return summary
    except Exception as e: 
        return ""

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



def storing_summary(summary: str ) -> dict:
    
    try:

        summary_embeddings = get_embeddings(summary)
        if not summary_embeddings:
            return {
                "error": "Failed to generate embeddings for summary."
            }

        # Connection Configuration
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=postgresql_password,
            host=host,
            port=port
        )
        cur = conn.cursor()

        # Store Summary in PostgreSQL
        try:
            store_query = """
                INSERT INTO all_document_summaries (summary_id , summary_text , summary_embedding ) 
                VALUES (%s, %s, %s )
            """
            cur.execute(
                store_query,
                (6  ,summary, summary_embeddings)
            )
            conn.commit()
            cur.close()
            conn.close()
            return {
                "res": "Summary stored successfully!"
            }
        except Exception as e:
            cur.close()
            conn.close()
            return {
                "error" :{e}
            } 
        
    except Exception as e:
        return {
            "error" :{e}
        }



# Storing chunks in PostgreSQL

def storing_chunks(chunks: list) -> dict:
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

        for index, chunk in enumerate(chunks):
            errors = []
            try:
                chunk_embeddings = get_embeddings(chunk.page_content)

                if not chunk_embeddings:
                    errors.append({"error" : f"Failed to generate embeddings for chunk {index + 1}."})
                    continue
                        
                store_query = """
                    INSERT INTO all_document_chunks (chunk_id , chunk_index , chunk_text , embedding )  
                    VALUES (%s, %s, %s , %s )
                """
                cur.execute(
                    store_query,
                    (index + 1000, index, chunk.page_content, chunk_embeddings)
                )
                conn.commit()
            except Exception as e:
                errors.append({"error" : f"Error storing chunk {index + 1} -> {e}"})
        
        cur.close()
        conn.close()
        return {
            "res": "Chunks stored successfully!",
            "errors": errors
        }

    except Exception as e:
        return{
            "error" :{e}
        }



def process_uploaded_documents(uploaded_file):
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_path = temp_file.name

    if uploaded_file.name.lower().endswith('.pdf'):
        loader = PyPDFLoader(temp_path)
    elif uploaded_file.name.lower().endswith('.txt'):
        loader = TextLoader(temp_path)
    else:
        os.unlink(temp_path)
        return {"error": "Unsupported file type. Please upload a PDF or TXT file."}

    docs = loader.load()
    os.unlink(temp_path)

    # Extract and chunk text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    chunks = text_splitter.split_documents(docs)

    page_content = " ".join([doc.page_content for doc in docs])

    # Generate Summary
    summary = generate_summary(page_content)
    if summary == "":
        return {
            "error": "Failed to generate summary."
        }

    # Store summary in PostgreSQL
    res = storing_summary(summary)
    if "error" in res:
        return res

    # Store chunks in PostgreSQL
    res = storing_chunks(chunks)
    if "error" in res:
        return res

    return {
        "res": "Ingestion pipeline completed successfully!"
    }



def main():
    # Load documents from directory
    loader = DirectoryLoader("../Documents/", glob="**/*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()

    # Extract and chunk text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    chunks = text_splitter.split_documents(documents)

    page_content = " ".join([doc.page_content for doc in documents])

    # Generate Summary
    summary = generate_summary(page_content)
    if summary:
        print("Summary generated successfully!")
    else:
        print("Failed to generate summary.")
        return {
            "error": "Failed to generate summary."
        }

    # Store summary in PostgreSQL
    res = storing_summary(summary)
    if "error" in res:
        print(f"Error storing summary: {res['error']}")
        return res
    else:
        print(res["res"])
    

    # Store chunks in PostgreSQL
    res = storing_chunks(chunks)
    if "error" in res:
        print(f"Errors storing chunks: {res['error']}")
        return res
    else:
        print(res["res"])

    return {
        "res": "Ingestion pipeline completed successfully!"
    }


if __name__ == "__main__":
    main()