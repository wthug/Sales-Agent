import os
import jwt
import datetime
import psycopg2
import psycopg2.extras
from functools import wraps
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sql_script import Database

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
            "message_id" : assistant_id
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
                assistant_time = datetime.datetime.now().strftime("%b %d, %Y, %I:%M %p")
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

if __name__ == "__main__":
   
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

