import asyncio
import os
import sys

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
        print("Fixing schema for: ai_provider_configs")
        try:
            # Check if column exists
            check_stmt = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'ai_provider_configs' AND column_name = 'model_parameters';
            """)
            result = await session.execute(check_stmt)
            if result.fetchone():
                print("Column 'model_parameters' already exists.")
                return

            # Add missing column
            print("Adding missing column 'model_parameters'...")
            alter_stmt = text("ALTER TABLE ai_provider_configs ADD COLUMN model_parameters JSON;")
            await session.execute(alter_stmt)
            await session.commit()
            print("Successfully added column 'model_parameters'.")

        except Exception as e:
            print(f"Error fixing schema: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(main())
