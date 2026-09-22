import os
import re

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

# ------------------------------------------------------------ follow-ups ----
# Six detractor reasons carry a follow-up question, each answered into its own
# sparse column. Keyed by the reason exactly as it is worded in [Reason]:
# matching is on that wording (normalised), never on loose keywords, because
# "Poor DOC quality" has a follow-up while "DOC prices are high" does not, and
# the neutral passive wording ("DOC quality") is a different reason again.
# Aliases list only variants seen in the data - do not guess new ones.
FOLLOW_UPS = {
    "Poor DOC quality": {
        "column": "if_reason_is_DOC_quality_what_did_you_observe",
        "question": "What did you observe?",
        "aliases": (),
    },
    "Poor DOC delivery service": {
        "column": "if_reason_is_delivery_service_what_can_be_improved",
        "question": "What can be improved?",
        "aliases": (),
    },
    "Poor Quality of feeds": {
        "column": "if_reason_is_quality_feeds_what_did_you_observe",
        "question": "What did you observe?",
        "aliases": (),
    },
    "Poor After-sales service": {
        "column": "if_reason_is_poor_after_sales_service__what_could_be_improved",
        "question": "What could be improved?",
        "aliases": ("Poor after sales service",),
    },
    "No market for MOCs": {
        "column": "if_reason_is_poor_access_to_MOC_market__what_could_be_improved",
        "question": "What could be improved?",
        "aliases": (),
    },
    "The Business was not profitable": {
        "column": "if_reason_is_business_was_not_profitable__what_could_be_improved",
        "question": "What could be improved?",
        "aliases": ("Business is not profitable", "The business is not profitable"),
    },
}

# column -> reason label, and every accepted wording -> reason label
_COLUMN_TO_REASON = {info["column"]: label for label, info in FOLLOW_UPS.items()}
FOLLOW_UP_SOURCE_COLUMNS = tuple(_COLUMN_TO_REASON)
FOLLOW_UP_LONG_COLS = ["Reason_Category", "Reason_Selected", "Follow_Up_Feedback"]

# values that mean "the customer did not answer this follow-up"
_BLANK_ANSWERS = {"", "nan", "none", "null", "n/a", "na", "-", "--", "nil"}


def _norm(text):
    """Letters and digits only, lowercased: 'Poor After-sales service' -> 'pooraftersalesservice'."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


_REASON_LOOKUP = {}
for _label, _info in FOLLOW_UPS.items():
    for _wording in (_label,) + tuple(_info.get("aliases", ())):
        _REASON_LOOKUP[_norm(_wording)] = _label


def clean_feedback(value):
    """Collapse whitespace and turn non-answers ('nan', 'N/A', ...) into ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = " ".join(str(value).split())
    return "" if text.lower() in _BLANK_ANSWERS else text


def followup_for_reason(reason):
    """{'reason', 'column', 'question'} for a reason that has a follow-up, else None."""
    label = _REASON_LOOKUP.get(_norm(reason))
    if not label:
        return None
    return {"reason": label, "column": FOLLOW_UPS[label]["column"],
            "question": FOLLOW_UPS[label]["question"]}


def followup_column_for_reason(reason):
    """Source column holding the follow-up answer for `reason` (None if it has none)."""
    info = followup_for_reason(reason)
    return info["column"] if info else None


def reason_category(reason):
    """Canonical reason label a wording maps to (None when it has no follow-up)."""
    return _REASON_LOOKUP.get(_norm(reason))


def _matching_reason_token(reason_value, label):
    """The token inside a comma-separated [Reason] cell that this follow-up belongs to."""
    for token in str(reason_value or "").split(","):
        token = token.strip()
        if token and _REASON_LOOKUP.get(_norm(token)) == label:
            return token
    return ""


def build_followup_feedback(df, groups=("Detractor",)):
    """Melt the sparse per-reason follow-up columns into one tidy frame.

    Returns one row per answered follow-up, carrying every original column plus:
      Reason_Category    - the reason whose follow-up question was answered
      Reason_Selected    - that reason as worded in this response's [Reason]
                           ('' when the follow-up was answered without picking it)
      Follow_Up_Feedback - the answer

    `groups` restricts to NPS groups (detractors by default); pass None for all.
    """
    present = [c for c in FOLLOW_UP_SOURCE_COLUMNS if c in df.columns]
    base = df
    if groups and "NPS_Group" in df.columns:
        base = df[df["NPS_Group"].isin(list(groups))]

    empty_cols = [c for c in df.columns if c not in present] + FOLLOW_UP_LONG_COLS
    if not present or base.empty:
        return pd.DataFrame(columns=empty_cols)

    id_vars = [c for c in base.columns if c not in present]
    long = base.melt(id_vars=id_vars, value_vars=present,
                     var_name="_followup_column", value_name="Follow_Up_Feedback")
    long["Follow_Up_Feedback"] = long["Follow_Up_Feedback"].map(clean_feedback)
    long = long[long["Follow_Up_Feedback"] != ""].copy()
    if long.empty:
        return pd.DataFrame(columns=empty_cols)

    long["Reason_Category"] = long["_followup_column"].map(_COLUMN_TO_REASON)
    if "Reason" in long.columns:
        long["Reason_Selected"] = [
            _matching_reason_token(reason, label)
            for reason, label in zip(long["Reason"], long["Reason_Category"])
        ]
    else:
        long["Reason_Selected"] = ""

    return long.drop(columns=["_followup_column"]).reset_index(drop=True)


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
      ,[if_reason_is_DOC_quality_what_did_you_observe]
      ,[if_reason_is_delivery_service_what_can_be_improved]
      ,[if_reason_is_quality_feeds_what_did_you_observe]
      ,[if_reason_is_poor_after_sales_service__what_could_be_improved]
      ,[if_reason_is_poor_access_to_MOC_market__what_could_be_improved]
      ,[if_reason_is_business_was_not_profitable__what_could_be_improved]
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

        # normalise the sparse follow-up answers once, so '' means "not answered"
        for col in FOLLOW_UP_SOURCE_COLUMNS:
            if col in df.columns:
                df[col] = df[col].map(clean_feedback)

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