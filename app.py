import streamlit as st
import pandas as pd
import plotly.express as px
from db import load_data

st.set_page_config(page_title="NPS Dashboard — Multi-Market", layout="wide", page_icon="📊")

# ====================== DESIGN SYSTEM (from Hatch HTML report, dark variant) ======================
ORANGE, ORANGE_LT = "#E65100", "#FFB74D"      # NPS / brand
GREEN,  GREEN_LT  = "#2E7D32", "#A5D6A7"      # Promoters
GREY,   GREY_LT   = "#9b9a94", "#d3d1c7"      # Passives
RED,    RED_LT    = "#C62828", "#EF9A9A"      # Detractors
NPS_TARGET = 50

FLAGS = {"Ethiopia": "🇪🇹", "Rwanda": "🇷🇼", "Uganda": "🇺🇬", "Kenya": "🇰🇪",
         "Ghana": "🇬🇭", "CDI": "🇨🇮", "Cote d'Ivoire": "🇨🇮", "Ivory Coast": "🇨🇮"}
def flag(c): return f"{FLAGS.get(str(c), '')} {c}".strip()

st.markdown("""
<style>
/* hide default chrome, tighten layout */
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.4rem; padding-bottom: 4.5rem;}

/* micro-labels like the report's .filter-label */
.hatch-label {font-size:11px; color:#888780; font-weight:700; letter-spacing:.07em; text-transform:uppercase; margin-bottom:6px;}

/* KPI cards — dark twins of the report's flat pastel cards */
.kpi {border-radius:12px; padding:18px 20px; border:1.5px solid;}
.kpi .lbl {font-size:12px; font-weight:600; margin-bottom:6px;}
.kpi .val {font-size:34px; font-weight:700; line-height:1;}
.kpi .sub {font-size:13px; margin-top:5px; color:#aaa89f;}
.kpi-nps {background:rgba(230,81,0,.13);  border-color:#E65100;} .kpi-nps .lbl,.kpi-nps .val {color:#FFB74D;}
.kpi-pro {background:rgba(46,125,50,.13); border-color:#2E7D32;} .kpi-pro .lbl,.kpi-pro .val {color:#A5D6A7;}
.kpi-pas {background:rgba(155,154,148,.12);border-color:#5f5e5a;} .kpi-pas .lbl,.kpi-pas .val {color:#d3d1c7;}
.kpi-det {background:rgba(198,40,40,.13); border-color:#C62828;} .kpi-det .lbl,.kpi-det .val {color:#EF9A9A;}
.kpi .ok {color:#A5D6A7;} .kpi .miss {color:#EF9A9A;}

/* report-style tables */
.htbl {width:100%; border-collapse:collapse; font-size:13px;}
.htbl th {text-align:left; padding:9px 10px; color:#e8e6e0; font-weight:700; border-bottom:2px solid #3a3a36;
          font-size:12px; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap;}
.htbl td {padding:8px 10px; border-bottom:.5px solid #2e2e2b; color:#dddbd4;}
.htbl tr:last-child td {border-bottom:none;}
.htbl .name {font-weight:700; color:#e8e6e0; white-space:nowrap;}
.htbl .num {text-align:center;}
.htbl .pct {font-weight:700;}
.htbl .cnt {font-size:11px; color:#888780; margin-left:4px; font-weight:400;}
.htbl .totals td {font-weight:700; border-top:2px solid #3a3a36; background:#232320;}
.badge {display:inline-block; padding:4px 11px; border-radius:99px; font-size:14px; font-weight:800;}
.b-pos {background:rgba(46,125,50,.25); color:#A5D6A7;}
.b-mid {background:rgba(230,81,0,.22);  color:#FFB74D;}
.b-neg {background:rgba(198,40,40,.25); color:#EF9A9A;}

/* reason-table group headers (pill style from the report) */
.rpill {display:inline-block; padding:5px 14px; border-radius:99px; font-size:12px; font-weight:700; margin-bottom:10px;}
.rpill-pro {background:rgba(46,125,50,.25); color:#A5D6A7;}
.rpill-pas {background:rgba(155,154,148,.22);color:#d3d1c7;}
.rpill-det {background:rgba(198,40,40,.25); color:#EF9A9A;}

/* sticky footer like the report */
.hatch-footer {position:fixed; left:0; right:0; bottom:0; background:#20201e; border-top:1px solid #3a3a36;
               padding:10px 24px; display:flex; justify-content:space-between; font-size:11px; color:#888780; z-index:99;}
.hatch-footer .formula {color:#b4b2a9; font-weight:500;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Hatch Africa / Agent NPS Dashboard")
st.markdown('<div class="hatch-label">Multi-Market · Internal Use Only</div>', unsafe_allow_html=True)

# ====================== LOAD DATA (unchanged) ======================
@st.cache_data(ttl=21600)
def get_data():
    return load_data()

df = get_data()

# ====================== FILTERS (unchanged logic) ======================
st.sidebar.header("🔍 Filters")
df['year'] = df['created_date'].dt.year
selected_years = st.sidebar.multiselect("Year", sorted(df['year'].unique()), default=[df['year'].max()])
mode = st.sidebar.radio("View by:", ["Weeks", "Months"], horizontal=True)
if mode == "Weeks":
    all_weeks = sorted(df['week'].unique())
    selected_weeks = st.sidebar.multiselect("Select Weeks", all_weeks, default=all_weeks[-8:])
    filtered_df = df[df['week'].isin(selected_weeks)]
else:
    all_months = sorted(df['month'].unique())
    selected_months = st.sidebar.multiselect("Select Months", all_months, default=all_months[-4:])
    filtered_df = df[df['month'].isin(selected_months)]
if selected_years:
    filtered_df = filtered_df[filtered_df['year'].isin(selected_years)]
countries = sorted(df['country'].dropna().unique())
selected_countries = st.sidebar.multiselect("Markets", countries, default=countries,
                                            format_func=flag)
if selected_countries:
    filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]
if len(filtered_df) == 0:
    st.error("No data for selected filters.")
    st.stop()

# ====================== KPI CARDS ======================
total = len(filtered_df)
prom = int((filtered_df['NPS_Group'] == 'Promoter').sum())
pas  = int((filtered_df['NPS_Group'] == 'Passive').sum())
det  = int((filtered_df['NPS_Group'] == 'Detractor').sum())
nps  = round((prom / total * 100) - (det / total * 100), 1) if total > 0 else 0

diff = round(nps - NPS_TARGET)
target_html = ('<span class="ok">✓ On target (50)</span>' if diff >= 0
               else f'<span class="miss">{diff:+d} vs target (50)</span>')

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f'<div class="kpi kpi-nps"><div class="lbl">NPS SCORE</div>'
            f'<div class="val">{nps:+.0f}</div><div class="sub">{target_html}</div></div>',
            unsafe_allow_html=True)
c2.markdown(f'<div class="kpi kpi-pro"><div class="lbl">PROMOTERS (9–10)</div>'
            f'<div class="val">{prom/total*100:.0f}%</div><div class="sub">{prom:,} calls</div></div>',
            unsafe_allow_html=True)
c3.markdown(f'<div class="kpi kpi-pas"><div class="lbl">PASSIVES (7–8)</div>'
            f'<div class="val">{pas/total*100:.0f}%</div><div class="sub">{pas:,} calls</div></div>',
            unsafe_allow_html=True)
c4.markdown(f'<div class="kpi kpi-det"><div class="lbl">DETRACTORS (1–6)</div>'
            f'<div class="val">{det/total*100:.0f}%</div><div class="sub">{det:,} calls</div></div>',
            unsafe_allow_html=True)

st.markdown("")

# ====================== COUNTRY + REGION COMPARISON ======================
st.subheader("Country & Region Comparison")
country_stats = filtered_df.groupby(['country', 'region']).agg(
    Promoters=('NPS_Group', lambda x: (x == 'Promoter').sum()),
    Passives=('NPS_Group', lambda x: (x == 'Passive').sum()),
    Detractors=('NPS_Group', lambda x: (x == 'Detractor').sum()),
    Total=('NPS_Group', 'count')
).reset_index()
for col in ['Promoters', 'Passives', 'Detractors', 'Total']:
    country_stats[col] = pd.to_numeric(country_stats[col])
country_stats['NPS'] = round((country_stats['Promoters'] / country_stats['Total'] * 100)
                             - (country_stats['Detractors'] / country_stats['Total'] * 100), 0)
country_stats = country_stats.sort_values('NPS', ascending=False)   # highest NPS first

def badge(v):
    cls = "b-pos" if v >= 30 else ("b-neg" if v < 0 else "b-mid")
    return f'<span class="badge {cls}">{v:+.0f}</span>'

def cell(count, total_, color):
    p = count / total_ * 100 if total_ else 0
    return (f'<td class="num"><span class="pct" style="color:{color}">{p:.0f}%</span>'
            f'<span class="cnt">({count:,})</span></td>')

rows = []
for _, r in country_stats.iterrows():
    rows.append(
        f'<tr><td class="name">{flag(r["country"])}</td><td>{r["region"]}</td>'
        + cell(r['Promoters'], r['Total'], GREEN_LT)
        + cell(r['Passives'],  r['Total'], GREY_LT)
        + cell(r['Detractors'],r['Total'], RED_LT)
        + f'<td class="num">{r["Total"]:,}</td><td class="num">{badge(r["NPS"])}</td></tr>'
    )
tp, tpa, td, tt = (country_stats['Promoters'].sum(), country_stats['Passives'].sum(),
                   country_stats['Detractors'].sum(), country_stats['Total'].sum())
tnps = round(tp / tt * 100 - td / tt * 100, 0) if tt else 0
rows.append('<tr class="totals"><td class="name">Hatch</td><td>—</td>'
            + cell(tp, tt, GREEN_LT) + cell(tpa, tt, GREY_LT) + cell(td, tt, RED_LT)
            + f'<td class="num">{tt:,}</td><td class="num">{badge(tnps)}</td></tr>')

st.markdown('<table class="htbl"><tr><th>Market</th><th>Region</th>'
            '<th class="num">Promoters</th><th class="num">Passives</th>'
            '<th class="num">Detractors</th><th class="num">Total</th><th class="num">NPS</th></tr>'
            + "".join(rows) + '</table>', unsafe_allow_html=True)

st.markdown("")

# ====================== WoW CHART ======================
st.subheader("NPS Movement — Week on Week")
weekly_nps = filtered_df.groupby(['week', 'country']).apply(
    lambda x: round(((x['NPS_Group'] == 'Promoter').sum() / len(x) * 100)
                    - ((x['NPS_Group'] == 'Detractor').sum() / len(x) * 100), 1) if len(x) > 0 else 0
).reset_index(name='NPS')
weekly_nps['_wk'] = weekly_nps['week'].str.extract(r'(\d+)').astype(int)
weekly_nps = weekly_nps.sort_values('_wk')

fig_wow = px.line(weekly_nps, x='week', y='NPS', color='country', markers=True, height=480)
fig_wow.update_layout(
    template='plotly_dark',
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#dddbd4'),
    legend=dict(orientation='h', y=1.08, title=None),
    xaxis=dict(gridcolor='#2e2e2b', title=None),
    yaxis=dict(gridcolor='#2e2e2b', title='NPS'),
    margin=dict(t=30, b=10),
)
fig_wow.add_hline(y=NPS_TARGET, line_dash="dot", line_color=ORANGE_LT,
                  annotation_text="Target 50", annotation_font_color=ORANGE_LT)
st.plotly_chart(fig_wow, use_container_width=True)

# ====================== REASONS ANALYSIS ======================
st.subheader("Reasons Analysis")

def reason_table(group, pill_cls, color):
    sub = filtered_df[filtered_df['NPS_Group'] == group]['Reason'] \
            .str.split(',').explode().str.strip()
    sub = sub[sub.notna() & (sub != '')]
    counts = sub.value_counts().head(12)
    mentions = sub.shape[0]  # % = share of total reason mentions for this group
    rows = "".join(
        f'<tr><td class="name" style="min-width:260px">{reason}</td>'
        f'<td class="num"><span class="pct" style="color:{color}">{cnt/mentions*100:.0f}%</span>'
        f'<span class="cnt">({cnt:,})</span></td></tr>'
        for reason, cnt in counts.items()
    )
    return ('<table class="htbl"><tr><th>Reason</th><th class="num">Share of mentions</th></tr>'
            + rows + '</table>')

tab_pro, tab_pas, tab_det = st.tabs(["Promoter Reasons", "Passive Reasons", "Detractor Reasons"])
with tab_pro:
    st.markdown('<span class="rpill rpill-pro">PROMOTER REASONS</span>', unsafe_allow_html=True)
    st.markdown(reason_table('Promoter', 'rpill-pro', GREEN_LT), unsafe_allow_html=True)
with tab_pas:
    st.markdown('<span class="rpill rpill-pas">PASSIVE REASONS</span>', unsafe_allow_html=True)
    st.markdown(reason_table('Passive', 'rpill-pas', GREY_LT), unsafe_allow_html=True)
with tab_det:
    st.markdown('<span class="rpill rpill-det">DETRACTOR REASONS</span>', unsafe_allow_html=True)
    st.markdown(reason_table('Detractor', 'rpill-det', RED_LT), unsafe_allow_html=True)

# ====================== FOOTER (report style) ======================
st.markdown('<div class="hatch-footer">'
            '<span>Hatch Africa · Internal use only · 🔄 Data refreshes every 6 hours</span>'
            '<span class="formula">NPS = % Promoters (9–10) − % Detractors (≤6)</span>'
            '</div>', unsafe_allow_html=True)
