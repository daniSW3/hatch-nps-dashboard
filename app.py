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

# preferred country order from the report (others appended alphabetically)
COUNTRY_ORDER = ["Ethiopia", "Rwanda", "Uganda", "Kenya", "Ghana", "CDI"]
def order_countries(cs):
    cs = list(cs)
    return [c for c in COUNTRY_ORDER if c in cs] + sorted([c for c in cs if c not in COUNTRY_ORDER])

st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.4rem; padding-bottom: 4.5rem;}
.hatch-label {font-size:11px; color:#888780; font-weight:700; letter-spacing:.07em; text-transform:uppercase; margin-bottom:6px;}
.kpi {border-radius:12px; padding:18px 20px; border:1.5px solid;}
.kpi .lbl {font-size:12px; font-weight:600; margin-bottom:6px;}
.kpi .val {font-size:34px; font-weight:700; line-height:1;}
.kpi .sub {font-size:13px; margin-top:5px; color:#aaa89f;}
.kpi-nps {background:rgba(230,81,0,.13);  border-color:#E65100;} .kpi-nps .lbl,.kpi-nps .val {color:#FFB74D;}
.kpi-pro {background:rgba(46,125,50,.13); border-color:#2E7D32;} .kpi-pro .lbl,.kpi-pro .val {color:#A5D6A7;}
.kpi-pas {background:rgba(155,154,148,.12);border-color:#5f5e5a;} .kpi-pas .lbl,.kpi-pas .val {color:#d3d1c7;}
.kpi-det {background:rgba(198,40,40,.13); border-color:#C62828;} .kpi-det .lbl,.kpi-det .val {color:#EF9A9A;}
.kpi .ok {color:#A5D6A7;} .kpi .miss {color:#EF9A9A;}
.htbl {width:100%; border-collapse:collapse; font-size:13px;}
.htbl th {text-align:center; padding:9px 10px; color:#e8e6e0; font-weight:700; border-bottom:2px solid #3a3a36;
          font-size:12px; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap;}
.htbl th:first-child {text-align:left;}
.htbl td {padding:8px 10px; border-bottom:.5px solid #2e2e2b; color:#dddbd4; text-align:center;}
.htbl td:first-child {text-align:left;}
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
.rpill {display:inline-block; padding:5px 14px; border-radius:99px; font-size:12px; font-weight:700; margin-bottom:10px;}
.rpill-pro {background:rgba(46,125,50,.25); color:#A5D6A7;}
.rpill-pas {background:rgba(155,154,148,.22);color:#d3d1c7;}
.rpill-det {background:rgba(198,40,40,.25); color:#EF9A9A;}
.mtbl {width:100%; border-collapse:collapse; font-size:13px;}
.mtbl th {padding:9px 10px; color:#e8e6e0; font-weight:700; border-bottom:2px solid #3a3a36;
          font-size:11px; text-transform:uppercase; letter-spacing:.03em; text-align:center; white-space:nowrap;}
.mtbl th:first-child {text-align:left; min-width:230px;}
.mtbl td {padding:7px 10px; border-bottom:.5px solid #2e2e2b; text-align:center; white-space:nowrap;}
.mtbl td:first-child {text-align:left; font-weight:700; color:#e8e6e0;}
.mtbl .pct {font-weight:700;} .mtbl .cnt {font-size:11px; color:#888780; margin-left:3px; font-weight:400;}
.hatch-footer {position:fixed; left:0; right:0; bottom:0; background:#20201e; border-top:1px solid #3a3a36;
               padding:10px 24px; display:flex; justify-content:space-between; font-size:11px; color:#888780; z-index:99;}
.hatch-footer .formula {color:#b4b2a9; font-weight:500;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Hatch Africa / Agent NPS Dashboard")
st.markdown('<div class="hatch-label">Multi-Market · Internal Use Only</div>', unsafe_allow_html=True)

@st.cache_data(ttl=21600)
def get_data():
    return load_data()

df = get_data()

# ====================== FILTERS ======================
df['week'] = df['created_date'].dt.strftime('%Y-W-%U')
df['month'] = df['created_date'].dt.strftime('%b-%y')

st.sidebar.header("🔍 Filters")
df['year'] = df['created_date'].dt.year

years = sorted(df['year'].unique())
selected_years = st.sidebar.multiselect("Year", years, default=[max(years)])
base = df[df['year'].isin(selected_years)] if selected_years else df

mode = st.sidebar.radio("View by:", ["Weeks", "Months"], horizontal=True)
if mode == "Weeks":
    all_weeks = sorted(base['week'].unique())
    selected_weeks = st.sidebar.multiselect("Select Weeks", all_weeks, default=all_weeks[-8:])
    if selected_weeks:
        base = base[base['week'].isin(selected_weeks)]
else:
    all_months = base.sort_values('created_date')['month'].unique().tolist()
    selected_months = st.sidebar.multiselect("Select Months", all_months, default=all_months[-4:])
    if selected_months:
        base = base[base['month'].isin(selected_months)]

countries = sorted(base['country'].dropna().unique())
selected_countries = st.sidebar.multiselect("Markets", countries, default=countries, format_func=flag)
if selected_countries:
    base = base[base['country'].isin(selected_countries)]

regions = sorted(base['region'].dropna().unique())
selected_regions = st.sidebar.multiselect("Regions", regions, default=regions)
if selected_regions:
    base = base[base['region'].isin(selected_regions)]

filtered_df = base
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
            f'<div class="val">{nps:+.0f}</div><div class="sub">{target_html}</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="kpi kpi-pro"><div class="lbl">PROMOTERS (9–10)</div>'
            f'<div class="val">{prom/total*100:.0f}%</div><div class="sub">{prom:,} calls</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="kpi kpi-pas"><div class="lbl">PASSIVES (7–8)</div>'
            f'<div class="val">{pas/total*100:.0f}%</div><div class="sub">{pas:,} calls</div></div>', unsafe_allow_html=True)
c4.markdown(f'<div class="kpi kpi-det"><div class="lbl">DETRACTORS (1–6)</div>'
            f'<div class="val">{det/total*100:.0f}%</div><div class="sub">{det:,} calls</div></div>', unsafe_allow_html=True)

st.markdown("")

# ====================== COUNTRY COMPARISON + SCORE DISTRIBUTION (side by side) ======================
left, right = st.columns([6, 4])

with left:
    st.subheader("Country comparison")
    # caption: total calls + the periods in view (weeks or months)
    if mode == "Weeks":
        periods = sorted(filtered_df['week'].unique())
    else:
        periods = filtered_df.sort_values('created_date')['month'].unique().tolist()
    period_txt = ", ".join(str(p) for p in periods)
    st.markdown(
        f'<div style="color:#888780;font-size:12px;margin:-6px 0 10px;">'
        f'{len(filtered_df):,} calls · {period_txt}</div>',
        unsafe_allow_html=True)
    country_stats = filtered_df.groupby('country').agg(
        Promoters=('NPS_Group', lambda x: (x == 'Promoter').sum()),
        Passives=('NPS_Group', lambda x: (x == 'Passive').sum()),
        Detractors=('NPS_Group', lambda x: (x == 'Detractor').sum()),
        Total=('NPS_Group', 'count')
    ).reset_index()
    for col in ['Promoters', 'Passives', 'Detractors', 'Total']:
        country_stats[col] = pd.to_numeric(country_stats[col])
    country_stats['NPS'] = round((country_stats['Promoters'] / country_stats['Total'] * 100)
                                 - (country_stats['Detractors'] / country_stats['Total'] * 100), 0)
    country_stats = country_stats.sort_values('NPS', ascending=False)

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
            f'<tr><td class="name">{flag(r["country"])}</td>'
            + cell(r['Promoters'], r['Total'], GREEN_LT)
            + cell(r['Passives'],  r['Total'], GREY_LT)
            + cell(r['Detractors'],r['Total'], RED_LT)
            + f'<td class="num">{badge(r["NPS"])}</td></tr>'
        )
    tp, tpa, td_, tt = (country_stats['Promoters'].sum(), country_stats['Passives'].sum(),
                        country_stats['Detractors'].sum(), country_stats['Total'].sum())
    tnps = round(tp / tt * 100 - td_ / tt * 100, 0) if tt else 0
    rows.append('<tr class="totals"><td class="name">Hatch</td>'
                + cell(tp, tt, GREEN_LT) + cell(tpa, tt, GREY_LT) + cell(td_, tt, RED_LT)
                + f'<td class="num">{badge(tnps)}</td></tr>')
    st.markdown('<table class="htbl"><tr><th>Market</th>'
                '<th class="num">Promoters</th><th class="num">Passives</th>'
                '<th class="num">Detractors</th><th class="num">NPS</th></tr>'
                + "".join(rows) + '</table>', unsafe_allow_html=True)

with right:
    st.subheader("Score Distribution")
    SCORE_GROUP = {10: ('Promoter', GREEN_LT), 9: ('Promoter', GREEN_LT),
                   8: ('Passive', GREY_LT), 7: ('Passive', GREY_LT)}
    sc = pd.to_numeric(filtered_df['Rating'], errors='coerce').dropna().astype(int)
    sc_total = len(sc)
    counts = sc.value_counts()
    maxc = counts.max() if len(counts) else 1
    rows = []
    for s in range(10, 0, -1):
        grp, color = SCORE_GROUP.get(s, ('Detractor', RED_LT))
        cnt = int(counts.get(s, 0))
        pct = cnt / sc_total * 100 if sc_total else 0
        bar = int(cnt / maxc * 90)
        rows.append(
            f'<tr><td style="text-align:center;font-weight:700;color:{color}">{s}</td>'
            f'<td style="text-align:left;color:{color}">{grp}</td>'
            f'<td style="text-align:right"><span style="display:inline-block;height:9px;width:{bar}px;'
            f'background:{color};border-radius:3px;margin-right:6px;vertical-align:middle"></span>{cnt:,}</td>'
            f'<td class="num">{pct:.0f}%</td></tr>'
        )
    st.markdown('<table class="htbl"><tr><th>Score</th><th style="text-align:left">Group</th>'
                '<th style="text-align:right">Count</th><th class="num">%</th></tr>'
                + "".join(rows) + '</table>', unsafe_allow_html=True)

st.markdown("")

# ====================== WoW CHART ======================
st.subheader("NPS Movement — Week on Week")
weekly_nps = filtered_df.groupby(['week', 'country']).apply(
    lambda x: round(((x['NPS_Group'] == 'Promoter').sum() / len(x) * 100)
                    - ((x['NPS_Group'] == 'Detractor').sum() / len(x) * 100), 1) if len(x) > 0 else 0
).reset_index(name='NPS')
weekly_nps = weekly_nps.sort_values('week')
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

# ====================== REASONS ANALYSIS (country matrix) ======================
st.subheader("Reasons Analysis")

def heat(color_rgb, pct):
    # opacity scales with % (caps ~50%), matching the report's heat shading
    a = min(pct / 50, 1) * 0.40
    return f'background:rgba({color_rgb},{a:.3f});'

def reason_matrix(group, pill_cls, label, color_lt, color_rgb):
    g = filtered_df[filtered_df['NPS_Group'] == group].copy()
    cs = order_countries(g['country'].dropna().unique())

    # explode reasons per row, keep country
    ex = g[['country', 'Reason']].copy()
    ex['Reason'] = ex['Reason'].str.split(',')
    ex = ex.explode('Reason')
    ex['Reason'] = ex['Reason'].str.strip()
    ex = ex[ex['Reason'].notna() & (ex['Reason'] != '')]

    # counts per reason x country, and Hatch total
    pivot = ex.pivot_table(index='Reason', columns='country', values=None,
                           aggfunc='size', fill_value=0)
    if pivot.empty:
        return f'<span class="rpill {pill_cls}">{label}</span><div style="color:#888;font-size:13px">No data.</div>'
    pivot['__total__'] = pivot.sum(axis=1)
    pivot = pivot.sort_values('__total__', ascending=False)

    col_totals = pivot.sum(axis=0)  # total mentions per column (denominator)
    hatch_total = col_totals['__total__']

    # header
    head = '<th>Reason</th><th>Hatch Total</th>' + "".join(f'<th>{flag(c)}</th>' for c in cs)
    body = ""
    for reason, r in pivot.iterrows():
        # Hatch total cell
        cnt_t = int(r['__total__']); p_t = cnt_t / hatch_total * 100 if hatch_total else 0
        cells = (f'<td style="{heat(color_rgb,p_t)}"><span class="pct" style="color:{color_lt}">{p_t:.0f}%</span>'
                 f'<span class="cnt">({cnt_t:,})</span></td>')
        for c in cs:
            cnt = int(r.get(c, 0)); denom = col_totals.get(c, 0)
            if cnt == 0:
                cells += '<td></td>'; continue
            p = cnt / denom * 100 if denom else 0
            cells += (f'<td style="{heat(color_rgb,p)}"><span class="pct" style="color:{color_lt}">{p:.0f}%</span>'
                      f'<span class="cnt">({cnt:,})</span></td>')
        body += f'<tr><td>{reason}</td>{cells}</tr>'
    return (f'<span class="rpill {pill_cls}">{label}</span>'
            f'<table class="mtbl"><tr>{head}</tr>{body}</table>')

tab_pro, tab_pas, tab_det = st.tabs(["Promoter Reasons", "Passive Reasons", "Detractor Reasons"])
with tab_pro:
    st.markdown(reason_matrix('Promoter', 'rpill-pro', 'PROMOTER REASONS', GREEN_LT, "46,125,50"), unsafe_allow_html=True)
with tab_pas:
    st.markdown(reason_matrix('Passive', 'rpill-pas', 'PASSIVE REASONS', GREY_LT, "120,120,116"), unsafe_allow_html=True)
with tab_det:
    st.markdown(reason_matrix('Detractor', 'rpill-det', 'DETRACTOR REASONS', RED_LT, "198,40,40"), unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown('<div class="hatch-footer">'
            '<span>Hatch Africa · Internal use only · 🔄 Data refreshes every 6 hours</span>'
            '<span class="formula">NPS = % Promoters (9–10) − % Detractors (≤6)</span>'
            '</div>', unsafe_allow_html=True)