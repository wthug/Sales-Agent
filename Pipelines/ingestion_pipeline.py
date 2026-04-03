from langchain_community.document_loaders import DirectoryLoader, TextLoader ,PyPDFLoader , Docx2txtLoader, UnstructuredPowerPointLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langsmith import traceable
from docx import Document


from pgvector.psycopg2 import register_vector
import psycopg2
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Extracting Variables from .env file
open_api_key = os.getenv("OPENAI_API_KEY")
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")

# Connection Configuration
conn = psycopg2.connect(
    dbname=db_name,
    user=user,
    password=postgresql_password,
    host=host,
    port=port
)

@traceable(run_type="chain", name="Document_Summarizer")
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
            ### ROLE
            You are a professional Summary Writing Agent. Your expertise lies in distilling complex information into concise, high-impact, and comprehensive summaries.

            ### TASK
            Read the provided input text and generate a professional summary of approximately 300 words. 
            
            ### CONSTRAINTS
            1. DO NOT include any introductory remarks, conversational filler, or explanations (e.g., "Here is the summary" or "This code defines...").
            2. DO NOT return code, function definitions, or markdown blocks.
            3. The output must be ONLY the summary itself.
            4. Return the result as a single, coherent paragraph that captures all key points and essential details.

            ### INPUT TEXT
            {text}

            ### SUMMARY
            """
        )
        chain = prompt | llm
        summary = chain.invoke({"text": input_text})
        print(summary)
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



def storing_summary(summary: str , document_id , doc: str, sharepoint_url: str) -> dict:
    try:
        summary_embeddings = get_embeddings(summary)
        if not summary_embeddings:
            return {
                "error": "Failed to generate embeddings for summary."
            }
        # Store Summary in PostgreSQL
        try:
            cur = conn.cursor()
            store_query = """
                INSERT INTO all_document_summaries ( document_id, summary_text , summary_embedding , document_name , document_sharepoint_url ) 
                VALUES ( %s, %s, %s, %s, %s )
            """
            cur.execute(
                store_query,
                ( document_id, summary, summary_embeddings, doc, sharepoint_url )
            )
            conn.commit()
            cur.close()
            return {
                "res": "Summary stored successfully!"
            }
        except Exception as e:
            cur.close()
            return {
                "error" :{e}
            } 
    except Exception as e:
        return {
            "error" :{e}
        }

# Storing chunks in PostgreSQL
def storing_chunks(chunks: list , document_id , doc: str, sharepoint_url: str) -> dict:
    try:
        cur = conn.cursor()
        errors = []
        print(len(chunks))
        number=0
        for index, chunk in enumerate(chunks):
            try:
                number+=1
                print(f"Chunk No:{number}")
                chunk_embeddings = get_embeddings(chunk)
                if not chunk_embeddings:
                    errors.append({"error" : f"Failed to generate embeddings for chunk {index + 1}."})
                    continue
                store_query = """
                    INSERT INTO all_document_chunks ( document_id, chunk_index , chunk_text , embedding , document_name , document_sharepoint_url )  
                    VALUES ( %s, %s , %s, %s , %s , %s )
                """
                cur.execute(
                    store_query,
                    ( document_id, index, chunk, chunk_embeddings, doc, sharepoint_url)
                )
                conn.commit()
            except Exception as e:
                errors.append({"error" : f"Error storing chunk {index + 1} -> {e}"})
        cur.close()
        return {
            "res": "Chunks stored successfully!",
            "errors": errors
        }
    except Exception as e:
        return{
            "error" :{e}
        }



def doc_loader_splitter(title):
    from collections import defaultdict

    doc = Document(title)

    sections = []

    current_section = {
        "heading": None,
        "content": "",
        "tables": []
    }

    for item in doc.iter_inner_content():  # Iterates paras + tables in order
        # print(item)
        if hasattr(item, 'style') and 'heading' in item.style.name.lower():
            # Save previous section
            if current_section["heading"]:
                sections.append(current_section)
            current_section["heading"] = item.text.strip()
            current_section["content"] = ""
            current_section["tables"] = []
        elif hasattr(item, 'table'):  # No, item is table
            # Convert table to dict
            table_data = []
            for row in item.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            # print(f"{table_data}\n")
            current_section["tables"].append(table_data)
        else:
            current_section["content"] += item.text + "  "

    
    if current_section["heading"]:
        sections.append(current_section)

    return sections

def row_to_str(row):
    """
    Converts a list (row) into a readable string: "ColName: Value | ColName: Value"
    """
    row_str = "..|"
    for item in row:
        row_str += f"{item} | "
    row_str += ".."
    return row_str

def prepare_llm_chunks(tables, heading, chunk_size=5):
    """
    Chunks tables into formatted strings optimized for LLM embeddings.
    """
    final_string_chunks = []

    for table in tables:
        if len(table) < 2:
            continue
            
        # Row 0 is the schema (e.g., "Name (str)")
        schema = table[0]
        data_rows = table[1:]
        
        for i in range(0, len(data_rows), chunk_size):
            current_batch = data_rows[i : i + chunk_size]
            
            # Start building the string for this specific chunk
            chunk_lines = []
            chunk_lines.append(f"{heading}\n")
            chunk_lines.append(row_to_str(schema))

            for row in current_batch:
                # Convert each row into a readable string: "ColName: Value | ColName: Value"
                chunk_lines.append(row_to_str(row))
            
            # Join everything with newlines to create one solid block of text
            
            chunk_str = "\n".join(chunk_lines)
            final_string_chunks.append(chunk_str)
            
    return final_string_chunks



def process_single_document(doc_tuple):
    document_id, doc, sharepoint_url, indexed = doc_tuple
    print("\n")
    print(f"Processing: {doc}")
    if doc.endswith('.pdf'):
        loader = DirectoryLoader("downloaded_documents", glob=f"**/{doc}", loader_cls=PyPDFLoader)
    elif doc.endswith('.txt'):
        loader = DirectoryLoader("downloaded_documents", glob=f"**/{doc}", loader_cls=TextLoader)
    elif doc.endswith('.docx'):
        loader = DirectoryLoader("downloaded_documents", glob=f"**/{doc}", loader_cls=Docx2txtLoader)
    elif doc.endswith('.pptx') or doc.endswith('.ppt'):
        loader = DirectoryLoader("downloaded_documents", glob=f"**/{doc}", loader_cls=UnstructuredPowerPointLoader)
    else:
        print(f"Unsupported file type for {doc}. Skipping.")
        return False
    

    try:
        loaded_doc = loader.load()  
        print(f"[OK] Loaded {doc} from directory.")
    except Exception as e:
        print(f"[FAIL] Error loading document {doc}: {e}")
        return False
    page_content = " ".join([d.page_content for d in loaded_doc])


    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    # Chunking 
    f=True
    # ....for docx
    if doc.endswith('.docx'):
        title = "./downloaded_documents/"+doc
        sections = doc_loader_splitter(title)
        if sections:
            f=False
            print(f"docx {doc} split by headers.......\n\n")
            chunks = []
            for section in sections:
                pre_chunks = text_splitter.split_text(section['content'])
                for chunk in pre_chunks:
                    chunks.append(f"{section['heading']}:\n\n{chunk}")
                table_chunks = prepare_llm_chunks(section['tables'], section['heading'])
                chunks.extend(table_chunks)
                


    # ....for pdfs , pptx and if docx fails
    if f:
        
        pre_chunks = text_splitter.split_documents(loaded_doc)
        chunks = []
        for chunk in pre_chunks:
            chunks.append(chunk.page_content)
        print(f"{doc} split by splitter.......\n\n")

    # for chunk in chunks:
    #     print(f"\n{len(chunk)}\n")
    #     print(chunk)
    #     print("\n----------------------------------------\n")

    # return 
    
    # Generate Summary
    summary = generate_summary(page_content)
    if summary == "":
        print(f"Failed to generate summary for {doc}. Skipping storage.")
        return False

    # Store summary in PostgreSQL
    res = storing_summary(summary, document_id, doc, sharepoint_url)
    if "error" in res:
        print(f"Error storing summary for {doc}: {res['error']}")
        return False
        
    print("Reached Chunking Phase")
    
    # Store chunks in PostgreSQL
    res = storing_chunks(chunks, document_id, doc, sharepoint_url)
    if "error" in res:
        print(f"Errors storing chunks for {doc}: {res['error']}")
        return False
        
    print(f"Done indexing {doc}")
    
    try:
        cur = conn.cursor()
        update_query = """
            UPDATE documents 
            SET indexed = TRUE , ingestion_status = 'completed' 
            WHERE file_name = %s
        """
        cur.execute(update_query, (doc.strip(),))
        conn.commit()
        cur.close()
    except Exception as e:
        cur.close()
        print(f"Error updating document status for {doc}: {e}")
        return False
        
    return True

def ingest_document_by_name(doc_name: str, sharepoint_url: str = ""):
    """
    Ingest a single document by name. If it doesn't exist in the database, 
    create a new record with the provided sharepoint_url and proceed.
    """
    try:
        cur = conn.cursor()
        search_query = """
            SELECT document_id, file_name, sharepoint_url, indexed
            FROM documents
            WHERE file_name = %s;
        """
        cur.execute(search_query, (doc_name,))
        doc_tuple = cur.fetchone()
        
        if not doc_tuple:
            print(f"Document '{doc_name}' not found in DB. Creating new entry...")
            insert_query = """
                INSERT INTO documents (file_name, sharepoint_url)
                VALUES (%s, %s)
                RETURNING document_id;
            """
            cur.execute(insert_query, (doc_name, sharepoint_url))
            document_id = cur.fetchone()[0]
            conn.commit()
            doc_tuple = (document_id, doc_name, sharepoint_url, False)
            
        cur.close()
    except Exception as e:
        print(f"Error handling document info for {doc_name}: {e}")
        return False

    return process_single_document(doc_tuple)

def upload_documents():
    docs = []
    try:
        cur = conn.cursor()
        search_query = """
            SELECT document_id , file_name , sharepoint_url , indexed
            FROM documents
            WHERE indexed = FALSE;
        """
        cur.execute(search_query)
        docs = cur.fetchall()
        cur.close()
    except Exception as e:
        cur.close()
        print(f"Error Fetching index pending documents : {e}")
        return

    print(f"\n\nUploading {len(docs)} documents in VectorDB....\n")
    for doc_tuple in docs:
        process_single_document(doc_tuple)
        break
        
    conn.close()
    print("\nAll documents uploaded successfully!\n\n")

if __name__ == "__main__":
    print("Select an ingestion option:")
    print("1. Process all pending documents from the database")
    print("2. Ingest a specific document by name from downloaded_documents")
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == '1':
        upload_documents()
    elif choice == '2':
        doc_name = input("Enter the exact file name (e.g., 'presentation.pptx'): ").strip()
        sharepoint_url = input("Enter the SharePoint URL (optional, press Enter to skip): ").strip()
        if doc_name:
            ingest_document_by_name(doc_name, sharepoint_url)
        else:
            print("Error: File name cannot be empty.")
    else:
        print("Invalid choice. Exiting.")
