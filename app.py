import streamlit as st
import pandas as pd
import plotly.express as px
from db import load_data

# Page Configuration
st.set_page_config(page_title="Hatch Agent NPS Dashboard", layout="wide", page_icon="📊")

st.title("📊 Agent NPS Dashboard — Multi-Market")
st.markdown("**Weeks 1–20** | Hatch Africa • Internal Use Only")

# ================== CACHED DATA LOADING ==================
@st.cache_data(ttl=21600)  # Cache for 6 hours
def get_data():
    return load_data()

df = get_data()

# ================== SIDEBAR FILTERS ==================
st.sidebar.header("🔍 Filters")

# Mode: Week or Month
mode = st.sidebar.radio("View by:", ["Weeks", "Months"], horizontal=True)

if mode == "Weeks":
    all_weeks = sorted(df['week'].unique())
    selected_weeks = st.sidebar.multiselect("Select Weeks", all_weeks, default=all_weeks[-8:])
    filtered_df = df[df['week'].isin(selected_weeks)]
else:
    all_months = sorted(df['month'].unique())
    selected_months = st.sidebar.multiselect("Select Months", all_months, default=all_months[-4:])
    filtered_df = df[df['month'].isin(selected_months)]

# Country Filter
countries = sorted(df['country'].dropna().unique())
selected_countries = st.sidebar.multiselect("Markets", countries, default=countries)

if selected_countries:
    filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]

# ================== KPI CARDS ==================
st.subheader("Key Metrics")

col1, col2, col3, col4 = st.columns(4)

total_calls = len(filtered_df)
promoters = len(filtered_df[filtered_df['NPS_Group'] == 'Promoter'])
passives = len(filtered_df[filtered_df['NPS_Group'] == 'Passive'])
detractors = len(filtered_df[filtered_df['NPS_Group'] == 'Detractor'])

nps_score = round(((promoters / total_calls) * 100) - ((detractors / total_calls) * 100), 1) if total_calls > 0 else 0

with col1:
    st.metric("**NPS Score**", f"{nps_score:+.1f}", help="NPS = % Promoters - % Detractors")
with col2:
    st.metric("Promoters (9-10)", promoters, f"{(promoters/total_calls*100):.1f}%")
with col3:
    st.metric("Passives (7-8)", passives, f"{(passives/total_calls*100):.1f}%")
with col4:
    st.metric("Detractors (≤6)", detractors, f"{(detractors/total_calls*100):.1f}%")

# ================== CHARTS ==================
tab1, tab2, tab3 = st.tabs(["📈 Overview", "💬 Reasons Analysis", "📋 Raw Data"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        st.subheader("NPS by Country")
        country_nps = filtered_df.groupby('country').apply(
            lambda x: round(((len(x[x['NPS_Group']=='Promoter'])/len(x))*100) -
                           ((len(x[x['NPS_Group']=='Detractor'])/len(x))*100), 1)
        ).reset_index(name='NPS')
        fig = px.bar(country_nps, x='country', y='NPS', color='NPS',
                     color_continuous_scale='RdYlGn', title="NPS Performance by Market")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Score Distribution")
        score_dist = filtered_df['Rating'].value_counts().sort_index()
        fig2 = px.bar(x=score_dist.index, y=score_dist.values, labels={'x':'Score', 'y':'Count'})
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Top Reasons by NPS Group")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**Promoters**")
        pro_reasons = filtered_df[filtered_df['NPS_Group']=='Promoter']['Reason'].str.split(',').explode().str.strip()
        st.dataframe(pro_reasons.value_counts().head(8), use_container_width=True)
    
    with c2:
        st.markdown("**Passives**")
        pas_reasons = filtered_df[filtered_df['NPS_Group']=='Passive']['Reason'].str.split(',').explode().str.strip()
        st.dataframe(pas_reasons.value_counts().head(8), use_container_width=True)
    
    with c3:
        st.markdown("**Detractors**")
        det_reasons = filtered_df[filtered_df['NPS_Group']=='Detractor']['Reason'].str.split(',').explode().str.strip()
        st.dataframe(det_reasons.value_counts().head(8), use_container_width=True)

with tab3:
    st.subheader("Raw Survey Data")
    st.dataframe(filtered_df, use_container_width=True, height=600)

# Footer
st.caption("🔄 Data refreshes every 6 hours | Powered by Hatch Data Warehouse")