# streamlit_app.py

import streamlit as st
from application import create_app

app = create_app()

# You can add Streamlit specific components here if needed
st.title("My Flask and Streamlit Application")

if __name__ == '__main__':
    from streamlit.web import cli as stcli
    import sys

    sys.argv = ["streamlit", "run", "streamlit_app.py"]
    sys.exit(stcli.main())
