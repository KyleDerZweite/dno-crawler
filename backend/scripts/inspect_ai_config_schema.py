import sys
import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import text

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env from project root
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))
load_dotenv(dotenv_path)

# Manually construct DATABASE_URL if not set
if not os.getenv("DATABASE_URL"):
    user = os.getenv("POSTGRES_USER", "dno")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    db = os.getenv("POSTGRES_DB", "dno_crawler")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

from app.db.database import get_db_session

async def main():
    async with get_db_session() as session:
        print("Inspecting table: ai_provider_configs")
        try:
            # Query information_schema to get columns
            stmt = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'ai_provider_configs'
                ORDER BY ordinal_position;
            """)
            result = await session.execute(stmt)
            columns = result.fetchall()
            
            if not columns:
                print("Table 'ai_provider_configs' does NOT exist.")
            else:
                print(f"Found {len(columns)} columns:")
                for col in columns:
                    print(f" - {col.column_name} ({col.data_type})")
                    
        except Exception as e:
            print(f"Error inspecting schema: {e}")

if __name__ == "__main__":
    asyncio.run(main())
