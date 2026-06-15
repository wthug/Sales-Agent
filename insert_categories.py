import os
import psycopg2
from dotenv import load_dotenv
from sql_script import Database

def insert_category():
    """
    Insert a category into the batch_categories table.
    Prompts user for category name, folder name, and description.
    """
    print("\n" + "="*60)
    print("       BATCH CATEGORY INSERTION TOOL")
    print("="*60 + "\n")
    
    # Get user inputs
    folder_name = input("Enter folder name: ").strip()
    if not folder_name:
        print("[ERROR] Folder name cannot be empty!")
        return False
    
    cat_name = input("Enter category name: ").strip()
    if not cat_name:
        print("[ERROR] Category name cannot be empty!")
        return False
    
    description = input("Enter description (optional, press Enter to skip): ").strip()
    if not description:
        description = None
    
    # Get database connection
    conn = Database.get_connection()
    if not conn:
        print("[ERROR] Failed to connect to database!")
        return False
    
    try:
        with conn.cursor() as cur:
            # Insert category
            cur.execute("""
                INSERT INTO batch_categories (folder_name, cat_name, description)
                VALUES (%s, %s, %s)
                RETURNING cat_id, folder_name, cat_name, description, created_at;
            """, (folder_name, cat_name, description))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                cat_id, folder, category, desc, created_at = result
                print("\n[SUCCESS] Category inserted successfully!")
                print(f"  Category ID: {cat_id}")
                print(f"  Folder Name: {folder}")
                print(f"  Category Name: {category}")
                print(f"  Description: {desc if desc else 'N/A'}")
                print(f"  Created At: {created_at}")
                return True
            
    except psycopg2.IntegrityError as e:
        conn.rollback()
        print(f"\n[ERROR] Category already exists for folder '{folder_name}' with name '{cat_name}'!")
        print(f"Details: {e}")
        return False
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Failed to insert category: {e}")
        return False
    finally:
        Database.put_connection(conn)


def insert_multiple_categories():
    """
    Insert multiple categories in one session.
    """
    print("\n" + "="*60)
    print("       BATCH CATEGORY INSERTION TOOL (Multiple)")
    print("="*60 + "\n")
    
    count = 0
    while True:
        print(f"\n--- Category #{count + 1} ---")
        
        folder_name = input("Enter folder name (or 'done' to finish): ").strip()
        if folder_name.lower() == 'done':
            break
        
        if not folder_name:
            print("[ERROR] Folder name cannot be empty!")
            continue
        
        cat_name = input("Enter category name: ").strip()
        if not cat_name:
            print("[ERROR] Category name cannot be empty!")
            continue
        
        description = input("Enter description (optional, press Enter to skip): ").strip()
        if not description:
            description = None
        
        # Get database connection
        conn = Database.get_connection()
        if not conn:
            print("[ERROR] Failed to connect to database!")
            continue
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO batch_categories (folder_name, cat_name, description)
                    VALUES (%s, %s, %s)
                    RETURNING cat_id;
                """, (folder_name, cat_name, description))
                
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    cat_id = result[0]
                    print(f"[SUCCESS] Category inserted with ID: {cat_id}")
                    count += 1
                
        except psycopg2.IntegrityError as e:
            conn.rollback()
            print(f"[ERROR] Category already exists for folder '{folder_name}' with name '{cat_name}'!")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to insert category: {e}")
        finally:
            Database.put_connection(conn)
    
    print(f"\n[INFO] Total categories inserted: {count}")


def main():
    """Main menu for category insertion."""
    print("\n" + "="*60)
    print("       BATCH CATEGORY INSERTION TOOL")
    print("="*60)
    print("\nOptions:")
    print("  1. Insert single category")
    print("  2. Insert multiple categories")
    print("  3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        insert_category()
        print("\n")
    elif choice == '2':
        insert_multiple_categories()
        print("\n")
    elif choice == '3':
        print("Exiting...")
    else:
        print("[ERROR] Invalid choice! Please enter 1, 2, or 3.")


if __name__ == "__main__":
    load_dotenv()
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Operation cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
