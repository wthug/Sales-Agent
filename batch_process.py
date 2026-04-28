# -*- coding: utf-8 -*-
import csv
import json
import os
import datetime
import urllib.request
import urllib.error
import getpass

def make_request(url, method="GET", headers=None, data=None):
    if headers is None:
        headers = {}
    
    req = urllib.request.Request(url, method=method, headers=headers)
    if data is not None:
        if isinstance(data, dict) or isinstance(data, list):
            req.data = json.dumps(data).encode('utf-8')
            req.add_header('Content-Type', 'application/json')
        else:
            req.data = data
            
    try:
        with urllib.request.urlopen(req) as response:
            response_body = response.read().decode('utf-8')
            if response_body:
                return json.loads(response_body)
            return {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        raise e
    except Exception as e:
        print(f"Error making request: {e}")
        raise e

def format_response(data):
    content = data.get("content", "No content generated.")
    sources_raw = data.get("sources", [])
    
    parsed_sources = []
    if isinstance(sources_raw, str):
        try:
            parsed_sources = json.loads(sources_raw)
        except json.JSONDecodeError:
            pass
    elif isinstance(sources_raw, list):
        parsed_sources = sources_raw
        
    source_map = {}
    doc_to_link = {}
    
    if parsed_sources:
        for doc in parsed_sources:
            name = doc.get("document_name")
            page = doc.get("page_number")
            url = doc.get("document_sharepoint_url")
            
            if name and page:
                if name not in source_map:
                    source_map[name] = []
                if page not in source_map[name]:
                    source_map[name].append(page)
            if name and url:
                if name not in doc_to_link:
                    doc_to_link[name] = url
                    
    formatted_sources = []
    if doc_to_link or source_map:
        for name in list(doc_to_link.keys()) + list(set(source_map.keys()) - set(doc_to_link.keys())):
            url = doc_to_link.get(name)
            pages = source_map.get(name, [])
            
            line = f"- {name}"
            if url:
                line += f" ({url})"
            if pages:
                line += f" ......Page numbers - {', '.join(map(str, pages))}"
            formatted_sources.append(line)
            
    return content, "\n".join(formatted_sources)

def main():
    print("=== Batch Question Processor ===")
    input_csv = input("Enter input CSV filename: ").strip()
    if not os.path.exists(input_csv):
        print(f"Error: File '{input_csv}' not found.")
        return
        
    api_url = input("Enter Base API URL (default 'http://localhost:8000'): ").strip()
    if not api_url:
        api_url = "http://localhost:8000"
        
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    url = f"{api_url}/api/login"
    payload = {
        "username": username,
        "password": password
    }
    
    try:
        login_res = make_request(url, method="POST", data=payload)
        token = login_res.get("token")
        if not token:
            print("Login failed: no token received.")
            return
        print("Login successful.")
    except Exception as e:
        print("Login failed. Exiting.")
        return
        
    output_csv = "output_" + os.path.basename(input_csv)
    
    # 1. Create a conversation
    csv_name = os.path.splitext(os.path.basename(input_csv))[0]
    print(f"\nCreating conversation with title: '{csv_name}'...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        conv_res = make_request(f"{api_url}/api/conversations", method="POST", headers=headers, data={"title": csv_name})
        conversation_id = conv_res.get("id")
        if not conversation_id:
            print("Failed to get conversation ID from response.")
            return
        print(f"Conversation created with ID: {conversation_id}")
    except Exception as e:
        print("Failed to create conversation. Exiting.")
        return
        
    print(f"\nProcessing rows. Output will be saved to '{output_csv}'...")
    
    with open(input_csv, 'r', encoding='utf-8-sig') as infile, \
         open(output_csv, 'w', encoding='utf-8-sig', newline='') as outfile:
         
        reader = csv.DictReader(infile)
        if 'Item' not in reader.fieldnames or 'Specification' not in reader.fieldnames:
            print(f"Error: Columns 'Item' and 'Specification' are required. Available columns: {reader.fieldnames}")
            return
            
        fieldnames = reader.fieldnames + ['AI Response', 'Sources']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        row_count = 0
        for row in reader:
            row_count += 1
            item = row.get('Item', '').strip()
            spec = row.get('Specification', '').strip()
            
            if not item and not spec:
                print(f"Row {row_count}: Empty Item and Specification. Skipping.")
                row['AI Response'] = ""
                row['Sources'] = ""
                writer.writerow(row)
                continue
                
            question = f"Item: {item}\nSpecification: {spec}"
            print(f"Row {row_count}: Processing question: {question[:50].replace(chr(10), ' ')}...")
            
            prompt_question = f"""
            Role & Objective  
            You are a Senior Solutions Consultant for SAS AML/CFT.
            Your task is to assess whether the solution addresses the client's requirement.
            Response Rules (MANDATORY):

            1. Start with a clear decision: "Yes" or "No".

            2. On the next line, state alignment:

            - "Fully Aligned"

            - "Partially Aligned"

            - "Not Aligned"

            3. Follow with a brief, client-friendly explanation (2-4 lines).

            - Keep it natural and professional.

            - Focus on business impact and clarity.

            - Avoid overly technical or robotic phrasing.
            
            Tone Guidelines:

            - Confident, concise, and human.

            - Engaging but not conversational or verbose.

            - No unnecessary validation phrases (e.g., "your requirement is correct").
            
            Strict Grounding:

            - Use only available knowledge.

            - If information is insufficient, respond:

            No  

            Not Aligned  

            The available information does not fully address this requirement.
            
            Product Context:

            Product: SAS AML/CFT
            
            Question:

            {question}
            
            """
            
            time_str = datetime.datetime.now().strftime('%b %d, %Y, %I:%M %p')
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt_question,
                        "time": time_str
                    }
                ],
                "conversation_id": conversation_id
            }
            
            try:
                chat_res = make_request(f"{api_url}/api/chat", method="POST", headers=headers, data=payload)
                content, sources = format_response(chat_res)
                row['AI Response'] = content
                row['Sources'] = sources
                print(f"  -> Success.")
            except Exception as e:
                print(f"  -> Failed to get response.")
                row['AI Response'] = f"ERROR: {str(e)}"
                row['Sources'] = ""
                
            writer.writerow(row)
            # Flush after every row so data is not lost if terminated
            outfile.flush()
            
    print(f"\nProcessing complete. {row_count} rows processed. Results saved to '{output_csv}'.")

if __name__ == "__main__":
    main()
