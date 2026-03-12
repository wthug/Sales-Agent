import streamlit as st


def main():
    st.title("Sales Agent Interface")
    st.write("Welcome to the Sales-Agent Streamlit UI!")

    user_input = st.text_input("Enter a message:")
    if st.button("Submit"):
        st.write(f"You entered: {user_input}")

    st.write("This is a simple starting point for the frontend.")


if __name__ == "__main__":
    main()
