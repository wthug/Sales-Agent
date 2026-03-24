import psycopg2
from psycopg2 import sql

from dotenv import load_dotenv
import os
load_dotenv()

db_name = os.getenv("db_name") 
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")


def create_tables():
    """Create tables in PostgreSQL database"""
    
    # Database connection parameters
    conn = psycopg2.connect(
        host=host,
        database=db_name,
        user=user,
        password = postgresql_password,
        port=port
    )
    
    cursor = conn.cursor()
    
    try:
        # Create folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id SERIAL PRIMARY KEY ,
                folder_name TEXT NOT NULL,
                sharepoint_path TEXT,
                parent_folder_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✓ folders table created")
        
        # Create documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                file_name TEXT NOT NULL,
                sharepoint_url TEXT,
                folder_id INT REFERENCES folders(folder_id),
                file_type TEXT,
                file_size BIGINT,
                created_date TIMESTAMP,
                modified_date TIMESTAMP,
                checksum TEXT,
                ingestion_status TEXT DEFAULT 'pending',
                indexed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✓ documents table created")
        
        # Create all_document_summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS all_document_summaries(
                summary_id SERIAL PRIMARY KEY,
                document_id UUID REFERENCES documents(document_id),
                folder_id INT REFERENCES folders(folder_id),
                summary_text TEXT,
                summary_embedding VECTOR(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                document_name TEXT,
                document_sharepoint_url TEXT
            );
        """)
        print("✓ all_document_summaries table created")
        
        # Create all_document_chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS all_document_chunks (
                chunk_id SERIAL PRIMARY KEY,
                document_id UUID REFERENCES documents(document_id),
                folder_id INT REFERENCES folders(folder_id),
                chunk_index INT,
                page_number INT,
                chunk_text TEXT,
                embedding VECTOR(384),
                token_count INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                document_name TEXT,
                document_sharepoint_url TEXT
            );
        """)
        print("✓ all_document_chunks table created")
        
        conn.commit()
        print("\n✓ All tables created successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating tables: {e}")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_tables()