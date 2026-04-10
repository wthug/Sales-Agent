
from langchain_core.tools import tool


@tool(
    description="Use this tool to get the documents related to any particular topic. Tree based structure is given where domain wise folders are there and inside that there are subfolders and documents related to that subfolder"
)
def get_structure():
    print("\n\nFetching folder structure...\n\n")
    tree_structure = "Below is tree structure of documents available in different domains, use this information to narrow down document to search through and query RAG tools accordingly\n\n"
    with open("../Pipelines/context_structure.txt", "r", encoding="utf-8") as f:
        tree_structure += f.read()

    return tree_structure

if __name__ == "__main__":
    
    tree_structure = get_structure()
    print(tree_structure)