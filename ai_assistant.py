"""
AI Assistant for the Hatch NPS Dashboard.

Adds a chat panel that answers questions about the data currently shown in
the dashboard (it respects the user's active filters).

How it works
------------
We do NOT send raw survey rows to the API. Instead we build a compact,
aggregated summary of the filtered data (KPIs, per-country stats, weekly
trend, top reasons, score distribution) and send that as context together
with the user's question. This keeps requests small, fast, cheap, and free
of customer-level personal data.

Setup
-----
1) requirements.txt  ->  add:  anthropic
2) Streamlit secrets ->  add:  ANTHROPIC_API_KEY = "sk-ant-..."
   (locally: put the same line in .env or export it)
3) app.py            ->  add two lines (see bottom of this file)
"""

import os
import pandas as pd
import streamlit as st

MODEL = "claude-haiku-4-5"       # fast + low cost; use "claude-sonnet-4-6" for deeper answers
MAX_TOKENS = 1000
MAX_HISTORY = 12                  # keep the last N chat turns


# ---------------------------------------------------------------- config --
def _get_key():
    """Streamlit secrets first (cloud), then environment / .env (local)."""
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


# ----------------------------------------------------- data -> compact text --
def _build_context(df: pd.DataFrame) -> str:
    """Aggregate the filtered dataframe into a compact text summary."""
    lines = []
    total = len(df)
    prom = int((df["NPS_Group"] == "Promoter").sum())
    pas = int((df["NPS_Group"] == "Passive").sum())
    det = int((df["NPS_Group"] == "Detractor").sum())
    nps = round(prom / total * 100 - det / total * 100, 1) if total else 0

    lines.append(f"OVERALL: {total:,} responses | NPS {nps:+.1f} (target 50) | "
                 f"Promoters {prom:,} ({prom/total*100:.0f}%) | "
                 f"Passives {pas:,} ({pas/total*100:.0f}%) | "
                 f"Detractors {det:,} ({det/total*100:.0f}%)")

    # periods in view
    weeks = sorted(df["week"].dropna().unique().tolist())
    if weeks:
        lines.append(f"WEEKS IN VIEW: {', '.join(map(str, weeks))}")

    # per-country table
    lines.append("BY COUNTRY (country | total | promoters | passives | detractors | NPS):")
    g = df.groupby("country")["NPS_Group"]
    for c, grp in df.groupby("country"):
        t = len(grp)
        p = int((grp["NPS_Group"] == "Promoter").sum())
        pa = int((grp["NPS_Group"] == "Passive").sum())
        d = int((grp["NPS_Group"] == "Detractor").sum())
        n = round(p / t * 100 - d / t * 100, 1) if t else 0
        lines.append(f"  {c} | {t:,} | {p:,} | {pa:,} | {d:,} | {n:+.1f}")

    # weekly NPS per country (trend)
    lines.append("WEEKLY NPS (week | country | NPS | responses):")
    for (w, c), grp in df.groupby(["week", "country"]):
        t = len(grp)
        p = int((grp["NPS_Group"] == "Promoter").sum())
        d = int((grp["NPS_Group"] == "Detractor").sum())
        n = round(p / t * 100 - d / t * 100, 1) if t else 0
        lines.append(f"  {w} | {c} | {n:+.1f} | {t:,}")

    # top reasons per NPS group (Hatch-wide)
    for grp_name in ("Promoter", "Passive", "Detractor"):
        sub = df[df["NPS_Group"] == grp_name]
        ex = sub["Reason"].dropna().str.split(",").explode().str.strip()
        ex = ex[ex != ""]
        top = ex.value_counts().head(10)
        denom = len(ex)
        lines.append(f"TOP {grp_name.upper()} REASONS (reason | mentions | % of {grp_name} mentions):")
        for r, cnt in top.items():
            lines.append(f"  {r} | {cnt:,} | {cnt/denom*100:.0f}%")

    # score distribution
    sc = pd.to_numeric(df["Rating"], errors="coerce").dropna().astype(int)
    vc = sc.value_counts().sort_index(ascending=False)
    dist = ", ".join(f"{s}:{c:,}" for s, c in vc.items())
    lines.append(f"SCORE DISTRIBUTION (score:count): {dist}")

    # per-region NPS within each country (kept short: only if <= 40 regions)
    if df["region"].nunique() <= 40:
        lines.append("BY REGION (country | region | total | NPS):")
        for (c, r), grp in df.groupby(["country", "region"]):
            if not str(r):
                continue
            t = len(grp)
            p = int((grp["NPS_Group"] == "Promoter").sum())
            d = int((grp["NPS_Group"] == "Detractor").sum())
            n = round(p / t * 100 - d / t * 100, 1) if t else 0
            lines.append(f"  {c} | {r} | {t:,} | {n:+.1f}")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are the analytics assistant inside Hatch Africa's Agent NPS dashboard.
You answer questions from business users about the NPS survey data summarised below.

Rules:
- Base every answer ONLY on the data summary provided. If the summary does not
  contain the information needed, say so plainly and suggest which dashboard
  filter or view might help.
- NPS = % Promoters (rating 9-10) minus % Detractors (rating <=6). Target is 50.
- Be concise and business-friendly: lead with the answer, then 1-3 supporting
  numbers. Use the exact figures from the summary; do not invent numbers.
- The summary reflects the user's CURRENT dashboard filters (year, weeks,
  markets, regions). Mention this if the user seems to expect all-time data.
- Amounts are survey call counts, not revenue.

DATA SUMMARY (current filters):
"""


# ------------------------------------------------------------------ UI ----
def render_ai_assistant(filtered_df: pd.DataFrame):
    """Chat panel. Call this from app.py with the filtered dataframe."""
    st.subheader("💬 Ask the data")
    st.markdown(
        '<div style="color:#888780;font-size:12px;margin:-6px 0 10px;">'
        'Answers are based on the data currently selected in your filters.</div>',
        unsafe_allow_html=True)

    api_key = _get_key()
    if not api_key:
        st.info("To enable the AI assistant, add `ANTHROPIC_API_KEY` to your "
                "Streamlit secrets (cloud) or `.env` (local), and add "
                "`anthropic` to requirements.txt.")
        return

    try:
        from anthropic import Anthropic
    except ImportError:
        st.error("The `anthropic` package is not installed. Add `anthropic` "
                 "to requirements.txt and redeploy.")
        return

    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    # replay history
    for m in st.session_state.ai_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    question = st.chat_input("e.g. Why is Kenya's NPS below target this month?")
    if not question:
        return

    st.session_state.ai_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # context is rebuilt each turn so it always matches the active filters
    context = _build_context(filtered_df)

    history = st.session_state.ai_messages[-MAX_HISTORY:]
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    with st.chat_message("assistant"):
        try:
            client = Anthropic(api_key=api_key)
            with st.spinner("Analysing…"):
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT + context,
                    messages=api_messages,
                )
            answer = "".join(b.text for b in resp.content if b.type == "text")
        except Exception as e:
            answer = f"Sorry — the assistant hit an error: {e}"
        st.markdown(answer)

    st.session_state.ai_messages.append({"role": "assistant", "content": answer})


# ---------------------------------------------------------------------------
# WIRING IT INTO app.py  (two lines)
# ---------------------------------------------------------------------------
# 1. At the top of app.py, with the other imports:
#
#       from ai_assistant import render_ai_assistant
#
# 2. Near the bottom of app.py — after the Reasons Analysis tabs and BEFORE
#    the footer — add:
#
#       st.markdown("")
#       render_ai_assistant(filtered_df)
#
# That's it. The assistant automatically answers based on whatever the user
# has filtered on screen.