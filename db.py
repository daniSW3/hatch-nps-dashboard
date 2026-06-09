import os
import inspect
import pytds
import pytds.login
import pandas as pd
import streamlit as st
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv()


def _cfg(key):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def _pytds_auth_debug():
    """Raise a descriptive error listing everything pytds exposes for auth."""
    login_exports = [x for x in dir(pytds.login) if not x.startswith("_")]
    pytds_exports = [x for x in dir(pytds) if not x.startswith("_")]
    azure_candidates = [
        x for x in pytds_exports + login_exports
        if any(k in x.lower() for k in ("azure", "ad", "auth", "fed", "token"))
    ]
    raise RuntimeError(
        f"pytds version: {getattr(pytds, '__version__', 'unknown')}\n"
        f"pytds.login exports: {login_exports}\n"
        f"Azure/auth candidates: {azure_candidates}"
    )


def load_data():
    _pytds_auth_debug()
