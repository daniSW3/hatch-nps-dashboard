import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    conn_str = (
        f"mssql+pyodbc://{os.getenv('CLIENT_ID')}:{os.getenv('CLIENT_SECRET')}"
        f"@{os.getenv('SERVER')}:1433/{os.getenv('DATABASE')}"
        f"?driver=ODBC+Driver+17+for+SQL+Server"
        f"&authentication=ActiveDirectoryServicePrincipal"
        f"&tenant_id={os.getenv('TENANT_ID')}"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=no"
    )
    return create_engine(conn_str, echo=False)

def load_data():
    """Load data from the view"""
    engine = get_engine()
    
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
    
    df = pd.read_sql(query, engine)
    
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
        except:
            return 'Unknown'
    
    df['NPS_Group'] = df['Rating'].apply(get_nps_group)
    
    return df