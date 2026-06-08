import os
import pandas as pd
import streamlit as st
import pytds
from pytds.login import AzureADPasswordAuth
from azure.identity import ClientSecretCredential
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


class _ServicePrincipalAuth(AzureADPasswordAuth):
    """
    Subclasses AzureADPasswordAuth so pytds recognises it during isinstance
    checks and sets the FedAuth flag in the prelogin packet, but overrides
    create_packet() to use the client-credentials OAuth flow instead of
    the resource-owner-password flow.
    """

    def __init__(self, tenant_id, client_id, client_secret):
        # Do NOT call super().__init__() — it expects a user/password for the
        # AAD password flow, which doesn't apply to service principals.
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    def create_packet(self):
        token = self._credential.get_token(
            "https://database.windows.net/.default"
        ).token
        return token.encode("utf-16-le")


def load_data():
    auth = _ServicePrincipalAuth(
        tenant_id=_cfg("TENANT_ID"),
        client_id=_cfg("CLIENT_ID"),
        client_secret=_cfg("CLIENT_SECRET"),
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

    with pytds.connect(
        dsn=_cfg("SERVER"),
        database=_cfg("DATABASE"),
        auth=auth,
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
