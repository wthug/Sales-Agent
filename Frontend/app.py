import os
import sys

import pandas as pd
import streamlit as st
import requests
from typing import List , Dict , Any

url = "http://localhost:8000/api/chat"

# Ensure we can import from project root (for Ingestion module)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    st.set_page_config(page_title="Sales Agent Portal", layout="wide")

    st.sidebar.title("Navigation")
    menu = st.sidebar.radio(
        "Go to:",
        ["💬 Chatbot" ,"📄 Upload Documents"]
    )

    # -----------------------------------------------------------------
    # Upload Documents
    # -----------------------------------------------------------------
    if menu == "📄 Upload Documents":
        st.title("📄 Document Upload")
        st.write("Upload files to build your Sales Agent knowledge base.")

        st.subheader("Upload Documents to Store (PDF / Docx)")
        user_input = st.file_uploader(
            "Upload a document to store in the knowledge base:",
            type=["pdf", "docx"],
            accept_multiple_files=False,
            key="reference_docs"
        )

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            store_btn = st.button("📝 Summarize and Store Document")
        with col2:
            clear_btn = st.button("🧹 Clear Uploaded File")

        if store_btn:
            if not user_input:
                st.error("Please upload a document first.")
            else:
                status_placeholder = st.empty()
                status_placeholder.info("Processing and storing document...")
                try:
                    from Ingestion.ingestion_pipeline import process_uploaded_documents
                    result = process_uploaded_documents(user_input)
                    if "error" in result:
                        status_placeholder.error("Couldn't complete due to error: " + str(result['error']))
                    else:
                        status_placeholder.success("Done! " + result["res"])
                        if "errors" in result:
                            st.warning("Some chunks had errors: " + str(result["errors"]))
                except Exception as e:
                    status_placeholder.error("Couldn't complete due to error: " + str(e))
                
        if clear_btn:
            st.warning("Please refresh the page to clear uploaded files.")

    # -----------------------------------------------------------------
    # Chatbot
    # -----------------------------------------------------------------
    else:
        st.title("💬 Sales Agent Chatbot")

        if "messages" not in st.session_state:
            st.session_state["messages"]    = []

        chat_box = st.container()

        with chat_box:
            for msg in st.session_state["messages"]:

                if msg["role"] == "user":
                    st.markdown(
                        f"""
                        <div style='background-color:#DCF8C6;padding:10px;border-radius:10px;
                        margin:5px 0;text-align:right'>🧑 {msg['content']}</div>
                        """,
                        unsafe_allow_html=True,
                    )

                else:
                    # 🤖 Assistant message
                    st.markdown(
                        f"""
                        <div style='background-color:#F1F0F0;padding:10px;border-radius:10px;
                        margin:5px 0;text-align:left'>🤖 {msg['content']}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if msg.get("sources"):
                        with st.expander("📄 View Sources"):
                            for src in msg["sources"]:
                                st.markdown(f"- {src}")

                            
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_input("💬 Type your message:")
            submitted = st.form_submit_button("Send")


        if submitted and user_input.strip():
            st.session_state["messages"].append({
                "role": "user", 
                "content": user_input.strip()
            })

            payload = {
                "messages": st.session_state["messages"].copy()
            }

            with chat_box:
                st.markdown(
                    f"""
                    <div style='background-color:#DCF8C6;padding:10px;border-radius:10px;
                    margin:5px 0;text-align:right'>🧑 {user_input.strip()}</div>
                    """,
                    unsafe_allow_html=True,
                )

            # Run agent
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(url, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        
                        ai_reply = f"{data["output"]}\n\n"
                        sources = []
                        if "documents_name" in data and len(data["documents_name"])>0:
                            sources = data["documents_name"]

                        print(sources)

                        # if document_url:
                        #     ai_reply += f"\n🔗 Link: {document_url}"

                    else:
                        ai_reply = f"⚠️ API Error:-> status code: {response.status_code} , message: {response.text}"
                        print("Error:", response.status_code, response.text)

                except Exception as e:
                    ai_reply = f"⚠️ Error: {e}"


            # Save assistant message
            st.session_state["messages"].append({
                "role": "assistant",
                "content": ai_reply,
                "sources": sources
            })


            with chat_box:
                st.markdown(
                    f"""
                    <div style='background-color:#F1F0F0;padding:10px;border-radius:10px;
                    margin:5px 0;text-align:left'>🤖 {ai_reply}</div>
                    """,
                    unsafe_allow_html=True,
                )
                if sources:
                    with st.expander("📄 View Sources"):
                        for src in sources:
                            st.markdown(f"- {src}")
                  

if __name__ == "__main__":
    main()
