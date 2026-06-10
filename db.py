import os
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def _get_setting(key):
    """Read from Streamlit secrets (cloud) first, then environment (.env locally)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)

def get_engine():
    conn_str = (
        f"mssql+pyodbc://{quote_plus(_get_setting('AZURE_CLIENT_ID'))}:{quote_plus(_get_setting('AZURE_CLIENT_SECRET'))}"
        f"@{_get_setting('DB_SERVER')}:1433/{_get_setting('DB_DATABASE')}"
        f"?driver=ODBC+Driver+17+for+SQL+Server"
        f"&authentication=ActiveDirectoryServicePrincipal"
        f"&tenant_id={_get_setting('AZURE_TENANT_ID')}"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=no"
    )
    return create_engine(conn_str, echo=False)

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
        except:
            return 'Unknown'
    
    df['NPS_Group'] = df['Rating'].apply(get_nps_group)
    
    return df