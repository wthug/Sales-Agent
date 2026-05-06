import os
import jwt
import datetime
import psycopg2
import psycopg2.extras
from functools import wraps
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_file
from sql_script import Database
import csv
import pandas as pd
from Agent.batch_agent import create_batch_agent

batch_agent = create_batch_agent()

from Agent.rag_agent import create_chat_agent
from langchain_core.documents import Document
from typing import List
import traceback
import json

app = Flask(__name__)

# Initialize database schema
Database.init_db()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-fallback-key")

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # We also need to support CORS preflight options so OPTIONS passes through if needed
        if request.method == "OPTIONS":
            return f(*args, **kwargs)
            
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "All fields (username, email, password) are required"}), 400
        
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    
    hashed_password = generate_password_hash(password)
    
    conn = Database.get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users ( username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, email, hashed_password)
            )
            new_user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"message": "User created successfully", "user_id": new_user_id}), 201
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Username already exists"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        Database.put_connection(conn)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password required"}), 400
        
    username = data["username"]
    password = data["password"]
    
    conn = Database.get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            
        if user and check_password_hash(user["password_hash"], password):
            token = jwt.encode({
                "user_id": user["id"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
            }, JWT_SECRET_KEY, algorithm="HS256")
            return jsonify({
                "token": token, 
                "username": user["username"],
                "message": "Login successful"
            }), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        Database.put_connection(conn)

# Create agent once at startup
agent = create_chat_agent()

@app.route("/api/conversations", methods=["GET", "OPTIONS"])
@require_token
def get_conversations():
    if request.method == "OPTIONS": return jsonify({}), 200
    conn = Database.get_connection()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT conversation_id, title, created_at, updated_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC", (request.user_id,))
            res = jsonify(cur.fetchall())
            # print(res)
            return res, 200
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: Database.put_connection(conn)

@app.route("/api/conversations", methods=["POST"])
@require_token
def create_conversation():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "New Conversation")
    
    conn = Database.get_connection()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING conversation_id", (request.user_id, title))
            conv_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"id": conv_id, "title": title}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally: Database.put_connection(conn)

@app.route("/api/conversations/<int:col_id>/messages", methods=["GET", "OPTIONS"])
@require_token
def get_messages(col_id):
    if request.method == "OPTIONS": return jsonify({}), 200
    conn = Database.get_connection()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT conversation_id FROM conversations WHERE conversation_id = %s AND user_id = %s", (col_id, request.user_id))
            if not cur.fetchone(): return jsonify({"error": "Conversation not found"}), 404
            cur.execute("SELECT message_id, role, content, sources, time_str, created_at FROM messages WHERE conversation_id = %s ORDER BY message_id ASC", (col_id,))
            return jsonify(cur.fetchall()), 200
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: Database.put_connection(conn)

@app.route("/api/chat", methods=["POST", "OPTIONS"])
@require_token
def chat_endpoint():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    messages = data.get("messages")
    conversation_id = data.get("conversation_id")
    # print(messages)
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages must be a list"}), 400
    try:
        # Save user message FIRST so it's visible if user switches chats
        user_msg = messages[-1]["content"] if messages else ""
        user_time = messages[-1].get("time", "") if messages else ""
        conn = Database.get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    if not conversation_id:
                        title = (user_msg[:30] + '...') if len(user_msg) > 30 else (user_msg or "New Conversation")
                        cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING conversation_id", (request.user_id, title))
                        conversation_id = cur.fetchone()[0]
                    cur.execute("INSERT INTO messages (conversation_id, role, content, time_str) VALUES (%s, %s, %s, %s)", (conversation_id, "user", user_msg, user_time))
                    
                    cur.execute("INSERT INTO messages (conversation_id, role,content, time_str) VALUES (%s, %s, %s, %s) RETURNING message_id", (conversation_id, "assistant", "Thinking...",user_time))
                    assistant_id = cur.fetchone()[0]
                    
                    cur.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s", (conversation_id,))
                conn.commit()
            except Exception as e:
                print("DB Error logging user msg:", e)
                conn.rollback()
            finally:
                Database.put_connection(conn)

        # Inject instruction so the LLM agent knows its message_id context dynamic variable
        if messages:
            messages[-1]["content"] += f"\n\n[SYSTEM INSTRUCTION: Your current message_id is {assistant_id}. You MUST pass msg_id={assistant_id} to any tool you call.]"

        response = agent.invoke({
            "messages": messages,
            "message_id" : assistant_id,
        })
        # print(response)
        # ✅ Final LLM response
        final_text = response["messages"][-1].content

        # ✅ Initialize result in NEW FORMAT
        result = {
            "content": final_text
        }
        
        # print("FINAL RESPONSE:", result)
        print("\n\n------returning final response-----\n")

        # Update Chat History
        conn = Database.get_connection()
        if conn:
            try:
                assistant_time = user_time
                with conn.cursor() as cur:
                    cur.execute("UPDATE messages SET content = %s, time_str = %s WHERE message_id = %s RETURNING sources", (result["content"], assistant_time, assistant_id))
                    sources = cur.fetchone()[0]
                    cur.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s", (conversation_id,))
                conn.commit()
                result["conversation_id"] = conversation_id
                result["time_str"] = assistant_time
                result["sources"] = sources
            except Exception as db_e:
                print("DB Error logging assistant msg:", db_e)
                conn.rollback()
            finally:
                Database.put_connection(conn)

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500    

@app.route("/api/batch_upload", methods=["POST", "OPTIONS"])
@require_token
def batch_upload():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Only .csv files are allowed"}), 400
        
    filename = secure_filename(file.filename)
    
    # Ensure directory exists
    if not os.path.exists("downloaded_documents"):
        os.makedirs("downloaded_documents")
        
    file_path = os.path.join("downloaded_documents", filename)
    file.save(file_path)
    
    # Extract additional fields if provided
    folder_name = request.form.get('folder_name', '')

    output_filename = f"output_{filename.rsplit('.', 1)[0]}.xlsx"
    user_id = getattr(request, 'user_id', None)
    
    conn = Database.get_connection()
    document_id = None
    task_id = None
    if conn:
        try:
            with conn.cursor() as cur:
                
                cur.execute("""
                    INSERT INTO batch_tasks (user_id, input_filename, output_filename)
                    VALUES (%s, %s, %s)
                    RETURNING task_id;
                """, (user_id, filename, output_filename))
                task_id = cur.fetchone()[0]
                conn.commit()
        except Exception as e:
            conn.rollback()
            print("DB Insert Error:", e)
        finally:
            Database.put_connection(conn)

    try:
        rows = _extract_rows_from_file(file_path)
        if not rows:
            return jsonify({"error": "No data rows found in the file. Ensure the file has 'Item' and 'Specification' columns."}), 400
        
        results = []
        total = len(rows)
        fn = folder_name.strip() if folder_name else None
        
        for idx, row_data in enumerate(rows):
            item = row_data['item']
            spec = row_data['specification']
            question = f"Item: {item}\nSpecification: {spec}"
            
            row_result = {
                "Row": idx + 1,
                "Item": item,
                "Specification": spec,
            }
            
            for skip_n in range(3):
                try:
                    augmented_question = (
                        f"{question}\n\n"
                        f"[CONTEXT: folder_name={fn}, file_name={output_filename}, index={idx}, skip={skip_n}]"
                    )
                    response = batch_agent.invoke({
                        "messages": [{"role": "user", "content": augmented_question}],
                    })
                    
                    ai_text = response["messages"][-1].content
                except Exception as e:
                    ai_text = f"Error: {str(e)}"
                
                row_result[f"AI Response {skip_n + 1}"] = ai_text
            
            results.append(row_result)
        
        # Fetch metadata and append to results
        conn = Database.get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT index, skip, metadata FROM metadata WHERE file_name = %s ORDER BY index ASC, skip ASC", 
                        (output_filename,)
                    )
                    metadata_rows = cur.fetchall()
                    
                    # Map metadata by (index, skip)
                    metadata_dict = {}
                    for row in metadata_rows:
                        key = (row[0], row[1])  # (index, skip)
                        metadata_dict[key] = row[2]
                    
                    def format_meta(raw_meta):
                        if raw_meta and isinstance(raw_meta, list):
                            parts = []
                            for i, doc in enumerate(raw_meta, 1):
                                doc_name = doc.get("document_name", "N/A")
                                doc_url = doc.get("document_sharepoint_url", "N/A")
                                folder = doc.get("folder_name", "N/A")
                                row_idx = doc.get("row_index", "N/A")
                                response = doc.get("Response", "N/A")
                                question = doc.get("Question", "N/A")
                                parts.append(
                                    f"Source {i}:\n"
                                    f"  Document: {doc_name}\n"
                                    f"  URL: {doc_url}\n"
                                    f"  Folder: {folder}\n"
                                    f"  Question: {question}\n"
                                    f"  Response: {response}\n"
                                    f"  Row Index: {row_idx}\n"
                                    f"  Similarity: {similarity}\n"
                                )

                            return "\n\n".join(parts)
                        return ""
                    
                    for res in results:
                        row_idx = res["Row"] - 1
                        for skip_n in range(3):
                            raw_meta = metadata_dict.get((row_idx, skip_n), None)
                            res[f"Metadata {skip_n + 1}"] = format_meta(raw_meta)
            except Exception as e:
                print("Error fetching metadata:", e)
            finally:
                Database.put_connection(conn)
            
        if not os.path.exists("processed_documents"):
            os.makedirs("processed_documents")
            
        output_path = os.path.join("processed_documents", output_filename)
        
        df = pd.DataFrame(results)
        df.to_excel(output_path, index=False)
        
        # Update status
        conn = Database.get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE batch_tasks SET status = 'successful' WHERE task_id = %s", (task_id,))
                conn.commit()
            except Exception as e:
                conn.rollback()
            finally:
                Database.put_connection(conn)
                
        return jsonify({"success": True, "task_id": task_id})
        
    except Exception as e:
        traceback.print_exc()
        if task_id:
            conn = Database.get_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE batch_tasks SET status = 'failed' WHERE task_id = %s", (task_id,))
                    conn.commit()
                except:
                    pass
                finally:
                    Database.put_connection(conn)
        return jsonify({"error": f"Failed to process batch: {str(e)}"}), 500

def _extract_rows_from_file(file_path: str) -> list:
    rows = []
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    def _parse_row(headers, cells):
        lower_headers = [str(h).strip().lower() for h in headers]
        cell_map = {
            lower_headers[i]: str(cells[i]).strip()
            for i in range(min(len(lower_headers), len(cells)))
        }
        item = cell_map.get('item', cells[0].strip() if cells else '')
        spec  = cell_map.get('specification', cells[1].strip() if len(cells) > 1 else '')
        return item, spec

    if ext == '.csv':
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = None
            for raw_row in reader:
                if not any(raw_row):
                    continue
                if headers is None:
                    headers = raw_row
                    continue
                item, spec = _parse_row(headers, raw_row)
                rows.append({'item': item, 'specification': spec})

    return rows

@app.route("/api/batch_history", methods=["GET", "OPTIONS"])
@require_token
def batch_history():
    if request.method == "OPTIONS": return jsonify({}), 200
    conn = Database.get_connection()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT task_id, input_filename, output_filename, status, created_at 
                FROM batch_tasks 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (request.user_id,))
            return jsonify(cur.fetchall()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        Database.put_connection(conn)

@app.route("/api/batch_download_file/<int:task_id>", methods=["GET", "OPTIONS"])
@require_token
def batch_download_file(task_id):
    if request.method == "OPTIONS": return jsonify({}), 200
    conn = Database.get_connection()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT output_filename FROM batch_tasks WHERE task_id = %s AND user_id = %s", (task_id, request.user_id))
            row = cur.fetchone()
            if not row: return jsonify({"error": "Task not found"}), 404
            
        file_path = os.path.join("processed_documents", row['output_filename'])
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found on disk"}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=row['output_filename'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        Database.put_connection(conn)

if __name__ == "__main__":
   
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

