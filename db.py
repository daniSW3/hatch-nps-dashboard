import os
import urllib.parse
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


def _cfg(key):
    # Prefer Streamlit secrets (cloud); fall back to .env (local)
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def get_engine():
    client_id = urllib.parse.quote_plus(_cfg("CLIENT_ID"))
    client_secret = urllib.parse.quote_plus(_cfg("CLIENT_SECRET"))
    server = _cfg("SERVER")
    database = _cfg("DATABASE")
    tenant_id = _cfg("TENANT_ID")

    conn_str = (
        f"mssql+pyodbc://{client_id}:{client_secret}"
        f"@{server}:1433/{database}"
        f"?driver=ODBC+Driver+17+for+SQL+Server"
        f"&authentication=ActiveDirectoryServicePrincipal"
        f"&tenant_id={tenant_id}"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=no"
    )
    return create_engine(conn_str, echo=False)


def load_data():
    engine = get_engine()

    query = """
    SELECT
        [id],
        [country],
        [created_date],
        [Rating],
        [Reason],
        [rsm],
        [region],
        [sr],
        [asm],
        [dispatch_date]
    FROM [silver].[Hatch_NPS_Report]
    WHERE created_date IS NOT NULL
    """

    df = pd.read_sql(query, engine)

    # Data Cleaning
    df['created_date'] = pd.to_datetime(df['created_date'])
    df['week'] = 'W' + df['created_date'].dt.strftime('%U')
    df['month'] = df['created_date'].dt.strftime('%Y-%m')

    # NPS Grouping
    def get_nps_group(rating):
        if pd.isna(rating):
            return 'Unknown'
        try:
            rating = int(float(rating))
            if rating >= 9:
                return 'Promoter'
            elif rating >= 7:
                return 'Passive'
            else:
                return 'Detractor'
        except Exception:
            return 'Unknown'

    df['NPS_Group'] = df['Rating'].apply(get_nps_group)

    return df
