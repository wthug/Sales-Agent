
import requests
import os
import psycopg2

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

tenant_id = os.getenv("tenant_id")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
SHAREPOINT_DOMAIN = os.getenv("SHAREPOINT_DOMAIN")

token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

token_data = {
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": "https://graph.microsoft.com/.default"
}

response = requests.post(token_url, data=token_data)
access_token = response.json().get("access_token")

if access_token:
    print("✅ Token generated")
else:
    print("❌ Token failed", response.text)
    exit()

headers = {
    "Authorization": f"Bearer {access_token}"
}   

# =========================
# 🌐 STEP 1: GET SITE
# =========================
site_url = "https://graph.microsoft.com/v1.0/sites/sutramanagement.sharepoint.com:/sites/SutraProposalsRepository"

response = requests.get(site_url, headers=headers)

if response.status_code != 200:
    print("❌ Site Error:", response.text)
    exit()

site_data = response.json()
site_id = site_data["id"]

print("✅ Site Found!")
print("Site ID:", site_id)


# =========================
# 📂 STEP 2: GET DEFAULT DOCUMENT LIBRARY
# =========================
drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"

response = requests.get(drive_url, headers=headers)

if response.status_code != 200:
    print("❌ Drive Error:", response.text)
    exit()

drive_data = response.json()
drive_id = drive_data["id"]

print("✅ Document Library Found:", drive_data["name"])


# create folder to store documents
DOWNLOAD_FOLDER = "downloaded_documents"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)



# Database connection configuration
db_name = os.getenv("db_name")
user = os.getenv("user")
postgresql_password = os.getenv("postgresql_password")
host = os.getenv("host")
port = os.getenv("port")

try:
    conn = psycopg2.connect(
        dbname=db_name,
        user=user,
        password=postgresql_password,
        host=host,
        port=port
    )
    print("Connected to PostgreSQL successfully!")
except Exception as e:
    print("❌ PostgreSQL Connection Error:", e)
    exit()


# Database update function 

def update_db(file_name, sharepoint_url = "youtube.com"):

    try:
        cur = conn.cursor()
        update_query = """
            INSERT INTO documents (file_name , sharepoint_url) 
            VALUES (%s, %s)
        """
        cur.execute(
            update_query ,
            (file_name, sharepoint_url)
        )

        conn.commit()
        cur.close() 
        print(f"Database updated with {file_name}")
    except Exception as e:
        cur.close()
        print(f"❌ Error updating database with {file_name}: {e}") 


# Download file from SharePoint

def download_file(drive_id, item_id, file_name ):
    download_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
    res = requests.get(download_url, headers=headers, stream=True)
    print(download_url)
    if res.status_code == 200:
        file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
        with open(file_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"⬇️ Downloaded: {file_name}")

        # Updating database with file name and sharepoint url
        update_db(file_name)

        

    else:
        print(f"❌ Failed to download {file_name}: {res.text}")
        



# Recursively get all items in the document library

def get_all_items(drive_id, folder="root", path=""):
    
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/{folder}/children"
    while url:
        res = requests.get(url, headers=headers)
        data = res.json()
        for item in data.get("value", []):
            current_path = f"{path}/{item['name']}"
            if "folder" in item:
                print(f"📁 {current_path}")
                get_all_items(drive_id,  f"items/{item['id']}", current_path)
            else:
                print(f"📄 {current_path}")

                # Cross check if file already exists to avoid duplicates
                if os.path.exists(os.path.join(DOWNLOAD_FOLDER, item["name"])):
                    print(f"⚠️ Skipping {item['name']} (already exists)")
                    continue                

                # ✅ DOWNLOAD ONLY PDF AND DOCX FILES
                if item["name"].lower().endswith(".pdf"):
                    download_file(drive_id, item["id"], item["name"])
                    
                # if item["name"].lower().endswith(".docx"):
                #     download_file(drive_id, item["id"], item["name"])


        url = data.get("@odata.nextLink")
    

def download_documents():
    print("Starting SharePoint document download...")
    get_all_items(drive_id )
    print("Download completed.")
    conn.close()

if __name__ == "__main__":
    download_documents()

