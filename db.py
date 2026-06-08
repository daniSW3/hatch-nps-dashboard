import os
import struct
import pandas as pd
import streamlit as st
import pyodbc
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv()

SQL_COPT_SS_ACCESS_TOKEN = 1256


def _cfg(key):
    # Prefer Streamlit secrets (cloud); fall back to .env (local)
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def _get_token_struct():
    credential = ClientSecretCredential(
        tenant_id=_cfg("TENANT_ID"),
        client_id=_cfg("CLIENT_ID"),
        client_secret=_cfg("CLIENT_SECRET"),
    )
    token = credential.get_token("https://database.windows.net/.default").token
    token_bytes = token.encode("UTF-16-LE")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _get_driver():
    available = [d for d in pyodbc.drivers() if "SQL Server" in d]
    for preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferred in available:
            return preferred
    if available:
        return available[0]
    raise RuntimeError(f"No SQL Server ODBC driver found. Installed drivers: {pyodbc.drivers()}")


def load_data():
    conn_str = (
        f"DRIVER={{{_get_driver()}}};"
        f"SERVER={_cfg('SERVER')},1433;"
        f"DATABASE={_cfg('DATABASE')};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

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

    with pyodbc.connect(
        conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: _get_token_struct()}
    ) as conn:
        df = pd.read_sql(query, conn)

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
