from flask import Flask, request, jsonify
from Agent.rag_agent import create_chat_agent
# from Pipelines.document_pipeline import download_documents
# from Pipelines.ingestion_pipeline import upload_documents
from langchain_core.documents import Document
from typing import List


app = Flask(__name__)

# Create agent once at startup
agent = create_chat_agent()


@app.route("/api/chat", methods=["POST"])
def chat_endpoint():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    messages = data.get("messages")

    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages must be a list"}), 400

    try:
        response = agent.invoke({
            "messages": messages
        })

        final_text = response["messages"][-1].content
        result = {
            "output" : final_text,
            "documents_name" : set()
        }

        docs: List[Document] = []

        for msg in reversed(response["messages"]):
            if msg.type == "tool" and hasattr(msg, "artifact"):
                docs = (msg.artifact)
                break
            
        for doc in docs:
            id, doc_text , doc_name, score  = doc
            result["documents_name"].add(doc_name) 
        # if len(docs)>0:
            # id,doc_text,doc_name,doc_sharepoint_url,score = docs[0]
            # id,doc_text,doc_name,score = docs[0]
            # result["document_sharepoint_url"] = doc_sharepoint_url 
        result["documents_name"]=list(result["documents_name"])
        print(result)
        return result

    except Exception as e:
        # print("here")
        return jsonify({
            "error": str(e)
        }), 500


import schedule
import time
import threading

# def run_task():
#     print("\n\nRunning at midnight....\n")
#     download_documents()
#     upload_documents()
#     print("\n\n...Task completed...\n")

# def scheduler_loop():
#     schedule.every().day.at("17:46").do(run_task)

#     while True:
#         schedule.run_pending()
#         time.sleep(60)

if __name__ == "__main__":
    # Start scheduler in background thread
    # t = threading.Thread(target=scheduler_loop, daemon=True)
    # t.start()

    # Start Flask app
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

# if __name__ == "__main__":
#     run_task()

