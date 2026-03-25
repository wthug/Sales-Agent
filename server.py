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

@app.route("/api/chat", methods=["POST", "OPTIONS"])
@require_token
def chat_endpoint():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    messages = data.get("messages")
    print(messages)
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages must be a list"}), 400
    try:
        response = agent.invoke({
            "messages": messages
        })
        print(response)
        # ✅ Final LLM response
        final_text = response["messages"][-1].content
        # ✅ Initialize result in NEW FORMAT
        result = {
            "content": final_text,
            "artifact": []
        }
        docs = []
        # 🔍 Extract tool artifact (latest tool call)
        for msg in reversed(response["messages"]):
            if msg.type == "tool" and hasattr(msg, "artifact") and msg.artifact:
                docs = msg.artifact
                break
        # ✅ Handle BOTH formats (old tuple + new dict)
        my_set = set()
        for doc in docs:
            try:
                # 🔹 NEW FORMAT (dict)
                if isinstance(doc, dict):
                    doc_name = doc.get("document_name")

                    if doc_name in my_set:
                        continue
                    my_set.add(doc_name)

                    result["artifact"].append({
                        "document_id": doc.get("document_id"),
                        "document_name": doc.get("document_name"),
                        "similarity": doc.get("similarity"),
                        "document_sharepoint_url":doc.get("document_sharepoint_url")
                    })
                # 🔹 OLD FORMAT (tuple)
                elif isinstance(doc, (list, tuple)) and len(doc) >= 5:
                    doc_id, doc_text, doc_name, score,document_sharepoint_url = doc

                    if doc_name in my_set:
                        continue
                    
                    my_set.add(doc_name)
                    

                    result["artifact"].append({
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "similarity": score,
                        "document_sharepoint_url": document_sharepoint_url
                    })
            except Exception as e:
                print("Error processing doc:", e)
        
        print("FINAL RESPONSE:", result)
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500    

if __name__ == "__main__":
   
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

