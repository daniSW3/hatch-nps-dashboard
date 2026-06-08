import os
import pandas as pd
import streamlit as st
import pytds
from azure.identity import ClientSecretCredential
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
    credential = ClientSecretCredential(
        tenant_id=_cfg("TENANT_ID"),
        client_id=_cfg("CLIENT_ID"),
        client_secret=_cfg("CLIENT_SECRET"),
    )
    server = _cfg("SERVER")
    database = _cfg("DATABASE")

    def connect():
        token = credential.get_token("https://database.windows.net/.default").token
        return pytds.connect(dsn=server, database=database, access_token=token)

    return create_engine("mssql+pytds://", creator=connect)


def load_data():
    """Load data from the view"""
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
