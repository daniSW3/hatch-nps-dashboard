import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load .env file and show debug info
load_dotenv()

def debug_env():
    """Helper to debug environment variables"""
    print("Current Working Directory:", os.getcwd())
    print(".env file exists:", os.path.exists('.env'))
    
    required_vars = ['DB_SERVER', 'DB_DATABASE', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'AZURE_TENANT_ID']
    for var in required_vars:
        value = os.getenv(var)
        print(f"{var}: {'***SET***' if value else 'MISSING'}")

def get_engine():
    required = {
        'SERVER': os.getenv('DB_SERVER'),
        'DATABASE': os.getenv('DB_DATABASE'),
        'CLIENT_ID': os.getenv('AZURE_CLIENT_ID'),
        'CLIENT_SECRET': os.getenv('AZURE_CLIENT_SECRET'),
        'TENANT_ID': os.getenv('AZURE_TENANT_ID')
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        raise Exception(
            f"❌ Missing environment variables: {', '.join(missing)}\n\n"
            f"Please make sure your .env file exists in the project root and contains all these variables."
        )

    conn_str = (
        f"mssql+pyodbc://{required['CLIENT_ID']}:{required['CLIENT_SECRET']}"
        f"@{required['SERVER']}:1433/{required['DATABASE']}"
        f"?driver=ODBC+Driver+17+for+SQL+Server"
        f"&authentication=ActiveDirectoryServicePrincipal"
        f"&tenant_id={required['TENANT_ID']}"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=yes"
        f"&timeout=60"
        f"&connect_timeout=60"
    )

    return create_engine(
        conn_str,
        echo=False,
        pool_pre_ping=True,
        pool_timeout=60,
        pool_recycle=1800
    )


def load_data():
    """Load data from the view"""
    try:
        engine = get_engine()

        query = """
        SELECT
            [id], [country], [created_date], [Rating], [Reason],
            [rsm], [region], [sr], [asm], [dispatch_date]
        FROM [silver].[Hatch_NPS_Report]
        WHERE created_date IS NOT NULL
        """

        df = pd.read_sql(query, engine)

        # Data processing
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
            except:
                return 'Unknown'

        df['NPS_Group'] = df['Rating'].apply(get_nps_group)

        return df

    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}") from e