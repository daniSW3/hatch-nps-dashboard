"""
AI Assistant for the Hatch NPS Dashboard  (v2 — with data-query tool).

The assistant now answers questions at ANY breakdown level: date (week/month),
country, region, RSM, ASM, NPS category and reasons — in any combination
(e.g. "biggest promoter driver in Central 1 region").

How it works
------------
1. A compact overall summary of the filtered data is sent as grounding.
2. The model also gets a `query_nps_data` TOOL. When a question needs a
   breakdown that isn't in the summary, the model calls the tool; we run the
   corresponding pandas groupby locally and return only the small aggregated
   result. Raw survey rows and customer IDs never leave the app.

Setup: requirements.txt -> anthropic | secrets -> ANTHROPIC_API_KEY
Wiring: from ai_assistant import render_ai_assistant ; render_ai_assistant(filtered_df)
"""

import os
import pandas as pd
import streamlit as st

MODEL = "claude-haiku-4-5"       # fast + low cost; use "claude-sonnet-4-6" for deeper answers
MAX_TOKENS = 1200
MAX_HISTORY = 12                  # keep the last N chat turns
MAX_TOOL_CALLS = 5                # per question
MAX_ROWS = 40                     # rows returned per tool call


# ---------------------------------------------------------------- config --
def _get_key():
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


# ------------------------------------------------------------- columns ----
def _cols(df):
    """Map friendly dimension names -> actual dataframe columns."""
    lower = {c.lower(): c for c in df.columns}
    def pick(*cands):
        for c in cands:
            if c in df.columns:
                return c
            if c.lower() in lower:
                return lower[c.lower()]
        return None
    m = {
        "country":   pick("country"),
        "region":    pick("region", "Region_Name"),
        "RSM":       pick("RSM"),
        "ASM":       pick("ASM"),
        "week":      pick("week"),
        "month":     pick("month"),
        "NPS_Group": pick("NPS_Group"),
        "Reason":    pick("Reason"),
    }
    return {k: v for k, v in m.items() if v is not None}


# ------------------------------------------------------------ query tool --
QUERY_TOOL = {
    "name": "query_nps_data",
    "description": (
        "Aggregate the NPS survey data currently shown on the dashboard. "
        "Use this whenever the user's question needs a breakdown not present "
        "in the summary (e.g. reasons per region, NPS per RSM per week). "
        "Group by any combination of: country, region, RSM, ASM, week, month, "
        "NPS_Group, Reason. Optional filters restrict rows first. "
        "If 'Reason' is in group_by, results are reason MENTION counts "
        "(one response can mention several reasons); otherwise results are "
        "response counts with Promoters/Passives/Detractors and NPS "
        "(NPS = %Promoters - %Detractors, target 50)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "group_by": {
                "type": "array",
                "items": {"type": "string",
                          "enum": ["country", "region", "RSM", "ASM",
                                   "week", "month", "NPS_Group", "Reason"]},
                "description": "Dimensions to group by (empty = overall totals).",
            },
            "filters": {
                "type": "object",
                "description": ("Optional filters, e.g. "
                                "{\"region\": [\"Central 1\"], \"NPS_Group\": [\"Promoter\"]}. "
                                "Keys: country, region, RSM, ASM, week, month, "
                                "NPS_Group, Reason. Values: list of strings."),
            },
            "top_n": {"type": "integer",
                      "description": f"Max rows to return (default 20, max {MAX_ROWS})."},
        },
        "required": ["group_by"],
    },
}


def _run_query(df, inp):
    """Execute a query_nps_data call with pandas. Returns a compact text table."""
    try:
        cols = _cols(df)
        d = df

        # ---- filters ----
        filters = inp.get("filters") or {}
        for key, vals in filters.items():
            col = cols.get(key)
            if col is None:
                continue
            if isinstance(vals, (str, int, float)):
                vals = [vals]
            vals_l = [str(v).strip().lower() for v in vals]
            if key == "Reason":
                d = d[d[col].fillna("").apply(
                    lambda s: any(v in [x.strip().lower() for x in str(s).split(",")]
                                  for v in vals_l))]
            else:
                d = d[d[col].astype(str).str.strip().str.lower().isin(vals_l)]

        if len(d) == 0:
            return "No rows match those filters (within the user's current dashboard selection)."

        group_by = [g for g in (inp.get("group_by") or []) if g in cols]
        top_n = max(1, min(int(inp.get("top_n", 20) or 20), MAX_ROWS))

        # ---- reason mention counts ----
        if "Reason" in group_by:
            ex = d.copy()
            rcol = cols["Reason"]
            ex[rcol] = ex[rcol].fillna("").str.split(",")
            ex = ex.explode(rcol)
            ex[rcol] = ex[rcol].str.strip()
            ex = ex[ex[rcol] != ""]
            gb = [cols[g] for g in group_by]
            out = (ex.groupby(gb).size().reset_index(name="mentions")
                     .sort_values("mentions", ascending=False).head(top_n))
            denom = len(ex)
            out["% of mentions"] = (out["mentions"] / denom * 100).round(1)
            header = " | ".join(group_by + ["mentions", "% of mentions"])
            lines = [header]
            for _, r in out.iterrows():
                lines.append(" | ".join([str(r[cols[g]]) for g in group_by]
                                        + [f"{int(r['mentions']):,}", f"{r['% of mentions']}%"]))
            lines.append(f"(total mentions in scope: {denom:,}; responses in scope: {len(d):,})")
            return "\n".join(lines)

        # ---- response counts + NPS ----
        d = d.copy()
        d["_p"] = (d[cols["NPS_Group"]] == "Promoter").astype(int)
        d["_pa"] = (d[cols["NPS_Group"]] == "Passive").astype(int)
        d["_d"] = (d[cols["NPS_Group"]] == "Detractor").astype(int)

        if not group_by:
            t, p, pa, dt = len(d), int(d["_p"].sum()), int(d["_pa"].sum()), int(d["_d"].sum())
            nps = round(p / t * 100 - dt / t * 100, 1)
            return (f"responses {t:,} | promoters {p:,} | passives {pa:,} | "
                    f"detractors {dt:,} | NPS {nps:+.1f}")

        gb = [cols[g] for g in group_by]
        out = d.groupby(gb).agg(responses=("_p", "size"), promoters=("_p", "sum"),
                                passives=("_pa", "sum"), detractors=("_d", "sum")).reset_index()
        out["NPS"] = ((out["promoters"] / out["responses"]
                       - out["detractors"] / out["responses"]) * 100).round(1)
        out = out.sort_values("responses", ascending=False).head(top_n)
        header = " | ".join(group_by + ["responses", "promoters", "passives", "detractors", "NPS"])
        lines = [header]
        for _, r in out.iterrows():
            lines.append(" | ".join([str(r[cols[g]]) for g in group_by]
                                    + [f"{int(r['responses']):,}", f"{int(r['promoters']):,}",
                                       f"{int(r['passives']):,}", f"{int(r['detractors']):,}",
                                       f"{r['NPS']:+.1f}"]))
        lines.append(f"(rows shown: {len(out)}; total responses in scope: {len(d):,})")
        return "\n".join(lines)

    except Exception as e:
        return f"Query failed: {e}"


# ----------------------------------------------------- overall summary ----
def _build_context(df: pd.DataFrame) -> str:
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
    weeks = sorted(df["week"].dropna().unique().tolist())
    if weeks:
        lines.append(f"WEEKS IN VIEW: {', '.join(map(str, weeks))}")
    lines.append("BY COUNTRY (country | total | NPS):")
    for c, grp in df.groupby("country"):
        t = len(grp)
        p = int((grp["NPS_Group"] == "Promoter").sum())
        dd = int((grp["NPS_Group"] == "Detractor").sum())
        n = round(p / t * 100 - dd / t * 100, 1) if t else 0
        lines.append(f"  {c} | {t:,} | {n:+.1f}")
    cols = _cols(df)
    dims = ", ".join(k for k in cols if k not in ("NPS_Group", "Reason"))
    lines.append(f"AVAILABLE BREAKDOWN DIMENSIONS: {dims}, NPS_Group, Reason")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are the analytics assistant inside Hatch Africa's Agent NPS dashboard.
You answer questions from business users about the NPS survey data.

Rules:
- The summary below covers the user's CURRENT dashboard filters. For any
  breakdown not in the summary (per region, RSM, ASM, week, month, reason,
  or combinations), CALL the query_nps_data tool instead of guessing or
  refusing. Prefer one or two well-chosen tool calls.
- NPS = % Promoters (rating 9-10) minus % Detractors (rating <=6). Target is 50.
- Base every number on the summary or on tool results. Never invent figures.
- Be concise and business-friendly: lead with the answer, then 1-3 supporting
  numbers.
- Amounts are survey call counts, not revenue.

DATA SUMMARY (current filters):
"""


# ------------------------------------------------------------------ UI ----
def render_ai_assistant(filtered_df: pd.DataFrame):
    st.subheader("💬 Ask the data")
    st.markdown(
        '<div style="color:#888780;font-size:12px;margin:-6px 0 10px;">'
        'Answers are based on the data currently selected in your filters. '
        'You can ask for breakdowns by week, month, market, region, RSM, ASM, '
        'NPS group or reason.</div>',
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
    for m in st.session_state.ai_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    question = st.chat_input("e.g. Biggest promoter driver in Central 1 region?")
    if not question:
        return

    st.session_state.ai_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    context = _build_context(filtered_df)
    history = st.session_state.ai_messages[-MAX_HISTORY:]
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    with st.chat_message("assistant"):
        try:
            client = Anthropic(api_key=api_key)
            with st.spinner("Analysing…"):
                resp = client.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT + context,
                    messages=api_messages, tools=[QUERY_TOOL],
                )
                calls = 0
                while resp.stop_reason == "tool_use" and calls < MAX_TOOL_CALLS:
                    tool_uses = [b for b in resp.content if b.type == "tool_use"]
                    api_messages.append({"role": "assistant", "content": resp.content})
                    results = []
                    for tu in tool_uses:
                        out = _run_query(filtered_df, tu.input or {})
                        results.append({"type": "tool_result",
                                        "tool_use_id": tu.id, "content": out})
                        calls += 1
                    api_messages.append({"role": "user", "content": results})
                    resp = client.messages.create(
                        model=MODEL, max_tokens=MAX_TOKENS,
                        system=SYSTEM_PROMPT + context,
                        messages=api_messages, tools=[QUERY_TOOL],
                    )
            answer = "".join(b.text for b in resp.content if b.type == "text") \
                     or "I couldn't produce an answer for that — try rephrasing."
        except Exception as e:
            answer = f"Sorry — the assistant hit an error: {e}"
        st.markdown(answer)

    st.session_state.ai_messages.append({"role": "assistant", "content": answer})