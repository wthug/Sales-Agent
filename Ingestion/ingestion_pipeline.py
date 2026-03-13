from langchain_community.document_loaders import DirectoryLoader, TextLoader ,PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate

from pgvector.psycopg2 import register_vector
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Extracting Variables from .env file
open_api_key = os.getenv("open_ai_key")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")


# Load documents from directory
loader = DirectoryLoader("../Documents/", glob="**/*.pdf", loader_cls=PyPDFLoader)
documents = loader.load()

# Extract and chunk text
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100
)

chunks = text_splitter.split_documents(documents)


def generate_summary(input_text: str) -> str:
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


def get_embeddings(input_text: str) -> list:
    embeddings = OpenAIEmbeddings(
        api_key=open_api_key,
        model="text-embedding-3-small",
        dimensions=384
    )
    embedding_vector = embeddings.embed_query(input_text)
    return embedding_vector


page_content = " ".join([doc.page_content for doc in documents])

# print(type(page_content))  # Print the first 500 characters of the page content for verification

summary = generate_summary(page_content)
# print(type(summary))
summary_embeddings = get_embeddings(summary)


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

# Store Summary in PostgreSQL
print("Storing Summary in PostgreSQL...")

try:
    
    search_query = """
        INSERT INTO all_document_summaries (summary_id , summary_text , summary_embedding ) 
        VALUES (%s, %s, %s )
    """

    cur.execute(
        search_query,
        (2  ,summary, summary_embeddings)
    )

    conn.commit()
    print("Summary stored successfully!")
except Exception as e:
    print(f"Error storing summary: {e}")


# Storing chunks in PostgreSQL
print("Storing Chunks in PostgreSQL...")

for index, chunk in enumerate(chunks):
    
    try:
        chunk_embeddings = get_embeddings(chunk.page_content)
        
        search_query = """
            INSERT INTO all_document_chunks (chunk_id , chunk_index , chunk_text , embedding )  
            VALUES (%s, %s, %s , %s )
        """
        
        cur.execute(
            search_query,
            (index + 1, index, chunk.page_content, chunk_embeddings)
        )
    except Exception as e:
        print(f"Error storing chunk {index + 1}: {e}")
conn.commit()

print("Chunks stored successfully!")

cur.close()
conn.close()


