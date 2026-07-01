import os

import certifi
import pandas as pd
import pytds
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv()

_SQL_SCOPE = "https://database.windows.net/.default"

REQUIRED_KEYS = [
    "DB_SERVER",
    "DB_DATABASE",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
]


def _cfg(key):
    """Streamlit secrets first (cloud), then environment / .env (local)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def debug_env():
    """Masked check of required config (safe to print)."""
    print("Current Working Directory:", os.getcwd())
    print(".env file exists:", os.path.exists(".env"))
    for var in REQUIRED_KEYS:
        print(f"{var}: {'***SET***' if _cfg(var) else 'MISSING'}")


def _check_config():
    missing = [k for k in REQUIRED_KEYS if not _cfg(k)]
    if missing:
        raise Exception(
            f"Missing configuration: {', '.join(missing)}. "
            "Set these in Streamlit secrets (cloud) or your .env file (local)."
        )


def _get_token() -> str:
    credential = ClientSecretCredential(
        tenant_id=_cfg("AZURE_TENANT_ID"),
        client_id=_cfg("AZURE_CLIENT_ID"),
        client_secret=_cfg("AZURE_CLIENT_SECRET"),
    )
    return credential.get_token(_SQL_SCOPE).token


def load_data():
    """Load data from the view."""
    try:
        _check_config()

        conn = pytds.connect(
            server=_cfg("DB_SERVER"),
            database=_cfg("DB_DATABASE"),
            access_token_callable=_get_token,
            cafile=certifi.where(),   # proper TLS validation (no TrustServerCertificate=yes)
            port=1433,
            login_timeout=60,
        )

        query = """
        SELECT  [id]
      ,[customer]
      ,[country]
      ,[created_date]
      ,[Rating]
      ,[Reason]
      ,[Sr_Name]
      ,[ASM]
      ,[RSM]
      ,[Region_Name]
      ,[dispatch_date]
       FROM [silver].[Hatch_NPS_Report]
       WHERE created_date IS NOT NULL
        """

        with conn:
            with conn.cursor() as cur:
                cur.execute(query)
                cols = [c[0] for c in cur.description]
                rows = cur.fetchall()

        df = pd.DataFrame(rows, columns=cols)

        # Data processing (unchanged)
        df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
        df['week'] = 'W' + df['created_date'].dt.strftime('%U')
        df['month'] = df['created_date'].dt.strftime('%Y-%m')

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

    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}") from e