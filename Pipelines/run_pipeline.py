

from ingestion_pipeline import upload_documents
from document_pipeline import download_documents

def run_task():
    print("\n\nRunning at midnight....\n")
    download_documents()
    upload_documents()
    print("\n\n...Task completed...\n")

if __name__ == "__main__":
    run_task()