import os
import psycopg2
from psycopg2 import pool
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

class Database:
    _connection_pool = None

    @classmethod
    def get_pool(cls):
        if cls._connection_pool is None:
            user = os.getenv("user", "postgres")
            password = os.getenv("postgresql_password", "")
            host = os.getenv("host", "localhost")
            port = os.getenv("port", "5432")
            dbname = os.getenv("db_name", "postgres")

            try:
                cls._connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    database=dbname
                )
                print("[OK] Database connection pool created successfully")
            except Exception as e:
                print("[FAIL] Error connecting to database:\n", e)
        return cls._connection_pool

    @classmethod
    def get_connection(cls):
        pool = cls.get_pool()
        if pool:
            return pool.getconn()
        return None

    @classmethod
    def put_connection(cls, conn):
        if cls._connection_pool and conn:
            cls._connection_pool.putconn(conn)

    @classmethod
    def init_db(cls):
        conn = cls.get_connection()
        if not conn:
            return
            
        try:
            with conn.cursor() as cur:
                # Users table
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("[OK] users table initialized")

                # Conversations table
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id SERIAL PRIMARY KEY,
                        user_id INT REFERENCES users(id) ON DELETE CASCADE,
                        title VARCHAR(255) DEFAULT 'New Conversation',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("[OK] conversations table initialized")

                # Messages table
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id SERIAL PRIMARY KEY,
                        conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        time_str VARCHAR(255),
                        sources JSONB DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("[OK] messages table initialized")

                # Folders table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS folders (
                        folder_id SERIAL PRIMARY KEY ,
                        folder_name TEXT NOT NULL,
                        sharepoint_path TEXT,
                        parent_folder_id INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                print("[OK] folders table initialized")
                
                # Documents table
                cur.execute("""
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
                print("[OK] documents table initialized")
                
                # all_document_summaries table
                cur.execute("""
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
                print("[OK] all_document_summaries table initialized")
                
                # all_document_chunks table
                cur.execute("""
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
                print("[OK] all_document_chunks table initialized")

            conn.commit()
            print("[OK] All database tables initialized successfully!")
        except Exception as e:
            print("[FAIL] Error initializing DB schema:", e)
        finally:
            cls.put_connection(conn)

if __name__ == "__main__":
    Database.init_db()