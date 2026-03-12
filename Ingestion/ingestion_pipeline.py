from langchain_community.document_loaders import DirectoryLoader, TextLoader ,PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

open_api_key = os.getenv("open_ai_key")

# Load documents from directory
loader = DirectoryLoader("../Documents/", glob="**/*.pdf", loader_cls=PyPDFLoader)
documents = loader.load()

# Extract and chunk text
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100
)

chunks = text_splitter.split_documents(documents)


def generate_summary(input_text: str) -> str:
    llm = OpenAI(
        api_key=open_api_key,
        temperature=0.7
    )
    prompt = PromptTemplate(
        input_variables=["text"],
        template="""
        Read the following text carefully. 
        Generate a comprehensive summary of approximately 300 words that captures all key points and essential details.

        Input Text:
        {text}

        Return the summary as a single, coherent paragraph that effectively conveys the main ideas and important information from the input text.
        """
    )
    chain = prompt | llm
    summary = chain.invoke({"text": input_text})
    return summary


def get_embeddings(input_text: str) -> list:
    embeddings = OpenAIEmbeddings(
        api_key=open_api_key,
        model="text-embedding-3-small",
        dimensions=384
    )
    embedding_vector = embeddings.embed_query(input_text)
    return embedding_vector



for documnet in documents:
    page_content = documnet.page_content


summary = generate_summary(page_content)

summary_embeddings = get_embeddings(summary)

chunk_embeddings = []

for chunk in chunks:
    chunk_embeddings.append(get_embeddings(chunk.page_content))


