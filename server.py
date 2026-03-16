from flask import Flask, request, jsonify
from Agent.rag_agent import create_chat_agent

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
        return final_text

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)