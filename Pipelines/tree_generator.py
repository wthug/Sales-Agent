def generate_tree(paths):
    # Step 1: Build a nested dictionary representing the folder structure
    tree = {}
    for path in paths:
        
        clean_path = path.replace("\\", "/")
        parts = clean_path.strip("/").split("/")
        
        current_node = tree
        for part in parts:
            if not part: 
                continue 
            if part not in current_node:
                current_node[part] = {}
            current_node = current_node[part]

    return build_tree_string(tree)

# Step 2: Recursively convert the dictionary into a formatted tree string
def build_tree_string(node, prefix=""):
    result = ""
    items = list(node.keys())
    
    for i, key in enumerate(items):
        is_last = (i == len(items) - 1)
        
        connector = "└── " if is_last else "├── "
        
        result += f"{prefix}{connector}{key}\n"
        
        extension = "    " if is_last else "│   "
        child_prefix = prefix + extension
        
        result += build_tree_string(node[key], child_prefix)
    return result



def generate_and_store_structure(path_strings):
    # Generate the tree structure 
    tree_output = generate_tree(path_strings)

    print("Generated Tree Structure:\n")
    print(tree_output)

    # Saving it to a text file 
    with open("context_structure.txt", "w", encoding="utf-8") as f:
        f.write(tree_output)
    
    print("Structure saved to context_structure.txt")

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    # 1. List of path strings
    path_strings = [
        "root/AML/aml_guidelines_2024.pdf",
        "root/AML/risk_assessment.docx",
        "root/ALM/asset_liability_q1.xlsx",
        "root/SAS Viya/deployment_guide.pdf",
        "root/SAS Viya/Architecture/system_design.txt"
    ]

    # 2. Generate the tree structure 
    tree_output = generate_tree(path_strings)

    print("Generated Tree Structure:\n")
    print(tree_output)

    # 3. Saving it to a text file 
    with open("context_structure.txt", "w", encoding="utf-8") as f:
        f.write("Folder structure of documents:\n\n")
        f.write(tree_output)
