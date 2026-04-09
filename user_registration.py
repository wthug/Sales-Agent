import requests

def register_user(username,email,password):
    url = "http://localhost:8000/api/register"
    payload = {"username": username, "email": email, "password": password}

    try:
        # Making the POST request
        response = requests.post(url, json=payload)
        
        # Check if successful
        response.raise_for_status() 
        
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error hitting API: {e}")


if __name__ == "__main__":
    username = input("Enter your username: ")
    email = input("Enter your email: ")
    password = input("Enter your password: ")
    register_user(username,email,password)