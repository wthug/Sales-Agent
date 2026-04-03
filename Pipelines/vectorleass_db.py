import psycopg2
from psycopg2 import extras
import uuid

import sys
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel

from new_splitter import doc_loading_lib

db_name = os.getenv("db_name")
user = os.getenv("user")
password = os.getenv("postgresql_password")  # Fixed to match .env
host = os.getenv("host")
port = os.getenv("port")

# Database connection parameters
DB_PARAMS = {
    "dbname": db_name,
    "user": user,
    "password": password,
    "host": host,
    "port": port
}


class state(BaseModel):
    node_id: int

def setup_postgres_db():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # 1. Create the Table
    # We use UUID for primary keys to avoid collisions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_tree (
            doc_id UUID PRIMARY KEY,
            parent_id UUID REFERENCES document_tree(doc_id),
            title TEXT NOT NULL,
            content TEXT,
            level INT DEFAULT 0
        );
    """)
    
    # 2. CREATE THE INDEX (This is the O(log n))
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parent_id ON document_tree(parent_id);")
    
    conn.commit()
    cur.close()
    conn.close()
    print("PostgreSQL Table and Index initialized.")

def insert_node(title, content, parent_id=None, level=0):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    new_id = str(uuid.uuid4())
    
    query = """
        INSERT INTO document_tree (doc_id, parent_id, title, content, level)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING doc_id;
    """
    
    cur.execute(query, (new_id, parent_id, title, content, level))
    node_id = cur.fetchone()[0]
    
    conn.commit()
    cur.close()
    conn.close()
    return node_id

def get_children(parent_id):
    conn = psycopg2.connect(**DB_PARAMS)
    # Using DictCursor lets us access columns by name (e.g., row['title'])
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # If parent_id is None, we are looking for the Root(s)
    if parent_id is None:
        query = "SELECT doc_id, title, content FROM document_tree WHERE parent_id IS NULL;"
        cur.execute(query)
    else:
        query = "SELECT doc_id, title, content FROM document_tree WHERE parent_id = %s;"
        cur.execute(query, (parent_id,))
    
    children = cur.fetchall()
    cur.close()
    conn.close()
    return children

def split_text(content: str, chunk_size: int = 80, chunk_overlap: int = 10):
    chunks = []
    titles = []
    
    if not content:
        return titles, chunks

    start = 0
    while start < len(content):
        end = start + chunk_size
        chunk = content[start:end]
        chunks.append(chunk)
        
        # getting first 5 words for title
        words = chunk.split()
        title = " ".join(words[:5])
        titles.append(title)
        
        if end >= len(content):
            break
        start += (chunk_size - chunk_overlap)
        
    return titles, chunks

def inject_document(title:str , parent_id=None):
    
    # Split into chunks
    sections = doc_loading_lib(title)

    # Form content
    content = ""
    for section in sections:
        content += section['heading'] + ":\n" + section['content'] + "\n\n"



    # Generate summary .... 
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = PromptTemplate(
        input_variables = ["content"] ,
        template = """
        Generate a three line summary of the given content.
        input format:
        content: {content}
        output format:
        summary
        """
    )

    chain = prompt | llm

    response = chain.invoke({"content": content})

    summary = response.content
    print(f"Summary generated....\n{summary} \n\n")


    #insert at level 1
    node_id = insert_node(title=title,content=summary,parent_id=parent_id,level=1)
    print(f"Summary inserted at level 1 with Node ID: {node_id}\n")

    #insert chunks at level 2
    # for i , chunk in enumerate(chunks):
    #     insert_node(title=titles[i],content=chunk,parent_id=node_id,level=2)
    #     print(f"Chunk {i+1} inserted at level 2 with Node ID: {node_id}\n")
    
    for section in sections:
        insert_node(title=section['heading'],content=section['content'],parent_id=node_id,level=2)
        
    print(f"Doc {title} inserted successfully!\n")
    return node_id

def find_out(user_query,node_id):
    
    children_docs = get_children(node_id)

    if not children_docs:
        return []
    
    res= ""
    for i,child in enumerate(children_docs):
        doc_id , title , content = child    
        res += f"Node ID: {i}\nTitle: {title}\nContent: {content}\n\n"
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    structured_llm = llm.with_structured_output(state)

    prompt = PromptTemplate(
        input_variables = ["user_query","documents"] ,
        template = """
        Given a user query and a list of documents, find the most relevant document to the query.
        return its Node ID
        input format:
        user query: {user_query}
        documents: {documents}
        output format:
        Node ID
        """
    )

    chain = prompt | structured_llm

    response = chain.invoke({"user_query": user_query, "documents": res})

    # print(f"{response}\n")
    child_id = response.node_id

    # print(child_id)

    answers = find_out(user_query,child_id)

    if answers:
        return answers
    
    for child in children_docs:
        doc_id , title , content = child
        if doc_id == child_id:
            return f"Title: {title}\nContent: {content}"

    return []


if __name__ == "__main__":
    # setup_postgres_db()
    # root_id = insert_node("root", "This is root node")
    # print(f"Root ID: {root_id}")

    # title1 = "Document about India"
    # text1 = """
    # India is a land where the ancient and the hyper-modern exist in a constant, vibrant dance. Stretching from the snow-capped peaks of the Himalayas to the tropical backwaters of Kerala, its geography is as diverse as its cultural fabric. To visit India is to experience a sensory explosion: the scent of jasmine and street food, the kaleidoscopic colors of traditional sarees, and a linguistic landscape featuring over 1,600 dialects. At its core, India is defined by a profound sense of continuity. It is one of the world’s oldest living civilizations, yet it currently stands as one of the fastest-growing major economies, positioning itself as a global leader in technology, pharmaceuticals, and space exploration.
    # The spirit of India is best captured in its philosophy of Vasudhaiva Kutumbakam—the world is one family. This ethos is reflected in its secular democracy, which manages to harmonize a multitude of religions, including Hinduism, Islam, Christianity, Sikhism, Buddhism, and Jainism. Beyond the bustling metropolises of Delhi and Mumbai lies a rural heartland where life follows the rhythm of the monsoons and local festivals. From the architectural marvel of the Taj Mahal to the spiritual ghats of Varanasi, the country offers a deep dive into human history. Today, India’s youth population is its greatest asset, driving an entrepreneurial revolution that seeks to blend traditional values with 21st-century innovation. It remains a nation that doesn't just change you; it expands your understanding of what it means to be alive.
    # """
    # title2 = "Document about France"
    # text2 = """
    # France is a nation that has mastered the "art de vivre" (the art of living), making it a global beacon for culture, philosophy, and elegance. Situated at the crossroads of Western Europe, its hexagonal borders contain a stunning variety of landscapes, from the rugged cliffs of Normandy to the sun-drenched lavender fields of Provence and the majestic French Alps. For centuries, France has been the epicenter of intellectual movements, giving birth to the Enlightenment and the principles of Liberté, Égalité, Fraternité. These values remain the bedrock of the French Republic, shaping a society that deeply respects civil liberties, secularism, and the rigors of intellectual debate.
    # The French identity is inextricably linked to its contributions to the arts and gastronomy. Paris, the "City of Light," serves as a living museum, housing icons like the Eiffel Tower and the Louvre, while the country’s culinary traditions are recognized by UNESCO as intangible cultural heritage. Whether it is the precision of a Michelin-starred meal or the simple perfection of a baguette from a village boulangerie, food is a serious pursuit here. Beyond the aesthetics, France is a powerhouse of industry and diplomacy, playing a pivotal role in the European Union and leading advancements in aerospace, high-speed rail, and luxury fashion. The French lifestyle encourages a balance between hard work and leisure, emphasizing the importance of taking time to appreciate beauty, conversation, and a glass of fine wine. It is a country that honors its past while fiercely debating its future, always with a signature sense of style.
    # """

    # print("Injecting doc 1\n")
    # # Inject a child document
    # child_id = inject_document(title1, text1, parent_id=root_id)
    

    # print("\nInjecting doc 2\n")
    # # Inject second child
    # child_id_2 = inject_document(title2, text2, parent_id=root_id)
    
    root_id = "e66f8f54-d9f1-408e-86fd-25609a2eeb67"

    # title = 'PNB_AML_Technical Proposal_v2.docx'

    # inject_document(title,parent_id=root_id)

    query = "What is the planned resource distribution for the full implementation of the project?"

    results = find_out(query,root_id)

    print(f"\n\nResults:\n")
    for result in results:
        print(result)
        print("\n----------------------------------------\n")

    # print("\n Running user query:  \n")
    # user_query = "what is the capital of France?"

    # results = find_out(user_query,root_id)
    # print(f"\n\nResults:\n{results}")
    # print(results)


    







