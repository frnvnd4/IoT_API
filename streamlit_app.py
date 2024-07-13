# streamlit_app.py

import streamlit as st
from application import create_app

app = create_app()

# Define the layout of your Streamlit app
st.title("My Flask and Streamlit Application")

# Running the Flask app
if 'flask_started' not in st.session_state:
    from threading import Thread

    def run_flask():
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()
    st.session_state.flask_started = True

st.write("Flask application is running...")
