import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# 1. Connection with Caching
@st.cache_resource
def get_engine():
    # Credentials stored securely in .streamlit/secrets.toml
    return create_engine(st.secrets["db_url"])

def load_data(query):
    engine = get_engine()
    return pd.read_sql(query, engine)

# 2. Simple Authentication
if st.text_input("Enter Passcode", type="password") != st.secrets["app_password"]:
    st.stop()

st.title("Haul247 Ops Intelligence")