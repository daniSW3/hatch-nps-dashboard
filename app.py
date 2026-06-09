import streamlit as st
import pandas as pd
import plotly.express as px
from db import load_data

st.set_page_config(page_title="NPS Dashboard — Multi-Market", layout="wide", page_icon="📊")

st.title("📊 Agent NPS Dashboard — Multi-Market")
st.markdown("**Weeks 1–** | Hatch Africa • Internal Use Only")

# ====================== LOAD DATA ======================
@st.cache_data(ttl=21600)
def get_data():
    return load_data()

df = get_data()

# ====================== FILTERS ======================
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
selected_countries = st.sidebar.multiselect("Markets", countries, default=countries)

if selected_countries:
    filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]

if len(filtered_df) == 0:
    st.error("No data for selected filters.")
    st.stop()

# ====================== KPI CARDS ======================
col1, col2, col3, col4 = st.columns(4)

total = len(filtered_df)
prom = len(filtered_df[filtered_df['NPS_Group'] == 'Promoter'])
pas = len(filtered_df[filtered_df['NPS_Group'] == 'Passive'])
det = len(filtered_df[filtered_df['NPS_Group'] == 'Detractor'])

nps = round(((prom / total) * 100) - ((det / total) * 100), 1) if total > 0 else 0

with col1:
    st.markdown('<div style="background:#FFF3E0;padding:20px;border-radius:12px;border:1.5px solid #FFB74D;text-align:center">', unsafe_allow_html=True)
    st.metric("NPS Score", f"{nps:+.0f}", "-15 vs target (50)")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div style="background:#F1F8F5;padding:20px;border-radius:12px;border:1.5px solid #A5D6A7;text-align:center">', unsafe_allow_html=True)
    st.metric("Promoters (9–10)", prom, f"{(prom/total*100):.0f}% of calls")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div style="background:#F7F7F5;padding:20px;border-radius:12px;border:1.5px solid #D3D1C7;text-align:center">', unsafe_allow_html=True)
    st.metric("Passives (7–8)", pas, f"{(pas/total*100):.0f}% of calls")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div style="background:#FFF5F5;padding:20px;border-radius:12px;border:1.5px solid #FFCDD2;text-align:center">', unsafe_allow_html=True)
    st.metric("Detractors (1–6)", det, f"{(det/total*100):.0f}% of calls")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== COUNTRY + REGION COMPARISON ======================
st.subheader("Country & Region Comparison")

country_stats = filtered_df.groupby(['country', 'region']).agg(
    Promoters=('NPS_Group', lambda x: (x == 'Promoter').sum()),
    Passives=('NPS_Group', lambda x: (x == 'Passive').sum()),
    Detractors=('NPS_Group', lambda x: (x == 'Detractor').sum()),
    Total=('NPS_Group', 'count')
).reset_index()

# Convert to numeric to avoid string division error
country_stats['Promoters'] = pd.to_numeric(country_stats['Promoters'])
country_stats['Passives'] = pd.to_numeric(country_stats['Passives'])
country_stats['Detractors'] = pd.to_numeric(country_stats['Detractors'])
country_stats['Total'] = pd.to_numeric(country_stats['Total'])

country_stats['NPS'] = round((country_stats['Promoters']/country_stats['Total']*100) - 
                            (country_stats['Detractors']/country_stats['Total']*100), 0)

st.dataframe(country_stats, use_container_width=True, hide_index=True)

# ====================== WoW CHART ======================
st.subheader("NPS Movement - Week on Week")

weekly_nps = filtered_df.groupby(['week', 'country']).apply(
    lambda x: round(((len(x[x['NPS_Group']=='Promoter'])/len(x))*100) - 
                   ((len(x[x['NPS_Group']=='Detractor'])/len(x))*100), 1) if len(x)>0 else 0
).reset_index(name='NPS')

fig_wow = px.line(weekly_nps, x='week', y='NPS', color='country', markers=True, height=500,
                  title="NPS Trend by Market (Week over Week)")
st.plotly_chart(fig_wow, use_container_width=True)

# ====================== REASONS ANALYSIS ======================
st.subheader("Reasons Analysis")

tab_pro, tab_pas, tab_det = st.tabs(["Promoter Reasons", "Passive Reasons", "Detractor Reasons"])

with tab_pro:
    st.markdown("**Promoter Reasons**")
    pro = filtered_df[filtered_df['NPS_Group']=='Promoter']['Reason'].str.split(',').explode().str.strip().value_counts().head(12)
    st.dataframe(pro, use_container_width=True)

with tab_pas:
    st.markdown("**Passive Reasons**")
    pasv = filtered_df[filtered_df['NPS_Group']=='Passive']['Reason'].str.split(',').explode().str.strip().value_counts().head(12)
    st.dataframe(pasv, use_container_width=True)

with tab_det:
    st.markdown("**Detractor Reasons**")
    detr = filtered_df[filtered_df['NPS_Group']=='Detractor']['Reason'].str.split(',').explode().str.strip().value_counts().head(12)
    st.dataframe(detr, use_container_width=True)

# Footer
st.caption("🔄 Data auto-refreshes every 6 hours | Hatch Africa • Internal Use Only")