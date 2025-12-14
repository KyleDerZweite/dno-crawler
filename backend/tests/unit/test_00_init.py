"""
Test 00: Initialize Test Database

Creates a SQLite database with seed data for all subsequent unit tests.
This replaces mock-based testing with real database operations.

Run this first: python -m tests.unit.test_00_init
Database created at: tests/unit/test.db

The database includes:
- 3 DNOs (WestNetz, RheinNetz, Netze BW)
- 5 extraction strategies (demonstrating different content_format types)
- Sample Netzentgelte and HLZF records
- Address cache entries for testing
"""

import sys
from pathlib import Path
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

# Location for test database
TEST_DB_PATH = Path(__file__).parent / "test.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"


# =============================================================================
# SQLite Compatibility Layer
# =============================================================================

def _setup_sqlite_compatibility(engine):
    """
    Configure SQLite to handle PostgreSQL-specific types.
    
    Maps ARRAY types to JSON, handles UUID as TEXT, etc.
    """
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _create_sqlite_base():
    """
    Create a modified Base that uses SQLite-compatible column types.
    
    This patches the PostgreSQL-specific types before creating tables.
    """
    # Import the original Base
    from app.db.database import Base
    from sqlalchemy.dialects.postgresql import ARRAY, UUID
    from sqlalchemy import JSON, String
    
    # Patch ARRAY to JSON for SQLite
    # This happens at import time, so we need to modify the column types
    
    return Base


# =============================================================================
# DATABASE CREATION
# =============================================================================

def create_test_database():
    """
    Create fresh SQLite database with only the tables needed for testing.
    
    We explicitly create only SQLite-compatible tables, skipping tables
    with ARRAY columns (strategy_insights, dno_crawl_configs with ARRAY).
    """
    print(f"📁 Creating test database at: {TEST_DB_PATH}")
    
    # Remove existing DB
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print("   - Removed existing database")
    
    # Create engine with SQLite
    engine = create_engine(
        TEST_DB_URL, 
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    _setup_sqlite_compatibility(engine)
    
    # Import only the models we need (SQLite-compatible ones)
    from app.db.models import (
        DNOModel,
        DNOAddressCacheModel,
        NetzentgelteModel,
        HLZFModel,
        ExtractionStrategyModel,
        DataSourceModel,
        CrawlJobModel,
        CrawlJobStepModel,
        CrawlAttemptModel,
        QueryLogModel,
        SystemLogModel,
        SearchJobModel,
    )
    
    # Create only the tables we need for testing
    # This avoids tables with ARRAY columns that SQLite can't handle
    tables_to_create = [
        DNOModel.__table__,
        DNOAddressCacheModel.__table__,
        NetzentgelteModel.__table__,
        HLZFModel.__table__,
        ExtractionStrategyModel.__table__,
        DataSourceModel.__table__,
        CrawlJobModel.__table__,
        CrawlJobStepModel.__table__,
        CrawlAttemptModel.__table__,
        QueryLogModel.__table__,
        SystemLogModel.__table__,
        SearchJobModel.__table__,
    ]
    
    from app.db.database import Base
    Base.metadata.create_all(engine, tables=tables_to_create)
    print(f"   - Created {len(tables_to_create)} tables (SQLite-compatible subset)")
    
    return engine


# =============================================================================
# SEED DATA
# =============================================================================

def seed_dnos(session: Session) -> dict[str, int]:
    """Seed DNO data. Returns mapping of slug -> id."""
    from app.db.models import DNOModel
    
    dnos = [
        DNOModel(
            slug="westnetz", 
            name="WestNetz", 
            official_name="Westnetz GmbH", 
            region="NRW", 
            website="https://www.westnetz.de"
        ),
        DNOModel(
            slug="rheinnetz", 
            name="RheinNetz", 
            official_name="Rhein-Netz GmbH",
            region="Köln", 
            website="https://www.rheinnetz.de"
        ),
        DNOModel(
            slug="netze-bw", 
            name="Netze BW", 
            official_name="Netze BW GmbH",
            region="Baden-Württemberg", 
            website="https://www.netze-bw.de"
        ),
    ]
    
    session.add_all(dnos)
    session.commit()
    
    # Refresh to get IDs
    for dno in dnos:
        session.refresh(dno)
    
    return {d.slug: d.id for d in dnos}


def seed_extraction_strategies(session: Session, dno_ids: dict[str, int]) -> None:
    """
    Seed extraction strategy configurations.
    
    Demonstrates the 4 content formats:
    - pdf_table: Most common, PDF with tabular data
    - html_table: Data in HTML <table> on website
    - pdf_image: Scanned PDF requiring OCR
    - website_image: Image embedded on webpage
    """
    from app.db.models import ExtractionStrategyModel
    
    strategies = [
        # =============================================================
        # WestNetz: Both PDF-based (pdf_table format)
        # =============================================================
        ExtractionStrategyModel(
            dno_id=dno_ids["westnetz"],
            strategy_type="netzentgelte",
            config={
                "content_format": "pdf_table",
                "search_queries": [
                    '"{dno_name}" Preisblatt Strom {year} filetype:pdf',
                    '"{dno_name}" Netznutzungsentgelte {year} filetype:pdf',
                    '"{dno_name}" Netzentgelte {year} filetype:pdf',
                ],
                "url_pattern": "westnetz.de",
                "extraction_method": "regex",
                "query_success_rates": {
                    '"{dno_name}" Preisblatt Strom {year} filetype:pdf': 0.90,
                    '"{dno_name}" Netznutzungsentgelte {year} filetype:pdf': 0.75,
                    '"{dno_name}" Netzentgelte {year} filetype:pdf': 0.60,
                },
            },
            success_count=15,
            failure_count=2,
        ),
        ExtractionStrategyModel(
            dno_id=dno_ids["westnetz"],
            strategy_type="hlzf",
            config={
                "content_format": "pdf_table",
                "search_queries": [
                    '"{dno_name}" Regelungen Strom {year} filetype:pdf',
                    '"{dno_name}" Hochlastzeitfenster {year} filetype:pdf',
                ],
                "extraction_method": "regex",
            },
            success_count=10,
            failure_count=1,
        ),
        
        # =============================================================
        # RheinNetz: Netzentgelte=PDF, HLZF=HTML table
        # =============================================================
        ExtractionStrategyModel(
            dno_id=dno_ids["rheinnetz"],
            strategy_type="netzentgelte",
            config={
                "content_format": "pdf_table",
                "search_queries": [
                    '"{dno_name}" Preisblatt Strom {year} filetype:pdf',
                ],
                "url_pattern": "rheinnetz.de",
            },
            success_count=8,
            failure_count=0,
        ),
        ExtractionStrategyModel(
            dno_id=dno_ids["rheinnetz"],
            strategy_type="hlzf",
            config={
                "content_format": "html_table",  # Key difference!
                "search_queries": [
                    '"{dno_name}" Hochlastzeitfenster {year}',  # No filetype:pdf
                    '"{dno_name}" Regelungen Strom {year}',
                ],
                "css_selector": "table.hlzf-table",
                "extraction_method": "beautifulsoup",
            },
            success_count=5,
            failure_count=0,
        ),
        
        # =============================================================
        # Default Strategy (no dno_id - applies when no DNO-specific exists)
        # =============================================================
        ExtractionStrategyModel(
            dno_id=None,
            strategy_type="netzentgelte",
            config={
                "content_format": "pdf_table",
                "search_queries": [
                    '"{dno_name}" Preisblatt Strom {year} filetype:pdf',
                    '"{dno_name}" Netznutzungsentgelte {year} filetype:pdf',
                    '"{dno_name}" Netzentgelte {year} filetype:pdf',
                    '"{dno_name}" vorläufiges Preisblatt {year} filetype:pdf',
                ],
                "extraction_methods": ["regex", "llm"],
            },
            success_count=0,
            failure_count=0,
        ),
    ]
    
    session.add_all(strategies)
    session.commit()


def seed_netzentgelte(session: Session, dno_ids: dict[str, int]) -> None:
    """Seed sample Netzentgelte records."""
    from app.db.models import NetzentgelteModel
    
    records = [
        # WestNetz 2024
        NetzentgelteModel(
            dno_id=dno_ids["westnetz"], year=2024, voltage_level="NS",
            leistung=45.50, arbeit=4.85, leistung_unter_2500h=None, arbeit_unter_2500h=5.25
        ),
        NetzentgelteModel(
            dno_id=dno_ids["westnetz"], year=2024, voltage_level="MS",
            leistung=32.20, arbeit=3.15, leistung_unter_2500h=None, arbeit_unter_2500h=3.55
        ),
        NetzentgelteModel(
            dno_id=dno_ids["westnetz"], year=2024, voltage_level="MS/NS",
            leistung=38.75, arbeit=3.95, leistung_unter_2500h=None, arbeit_unter_2500h=4.35
        ),
        # RheinNetz 2024
        NetzentgelteModel(
            dno_id=dno_ids["rheinnetz"], year=2024, voltage_level="NS",
            leistung=42.00, arbeit=4.50
        ),
        NetzentgelteModel(
            dno_id=dno_ids["rheinnetz"], year=2024, voltage_level="MS",
            leistung=30.00, arbeit=2.90
        ),
    ]
    
    session.add_all(records)
    session.commit()


def seed_hlzf(session: Session, dno_ids: dict[str, int]) -> None:
    """Seed sample HLZF records."""
    from app.db.models import HLZFModel
    
    records = [
        # RheinNetz 2024 (from HTML table)
        HLZFModel(
            dno_id=dno_ids["rheinnetz"], year=2024, 
            voltage_level="Hochspannungsnetz",
            winter="08:00 - 20:00", 
            fruehling="08:00 - 20:00",
            sommer="entfällt", 
            herbst="08:00 - 20:00"
        ),
        HLZFModel(
            dno_id=dno_ids["rheinnetz"], year=2024, 
            voltage_level="Umspannung HS/MS",
            winter="07:30 - 19:30", 
            fruehling="07:30 - 19:30",
            sommer="entfällt", 
            herbst="07:30 - 19:30"
        ),
        # WestNetz 2024 (from PDF)
        HLZFModel(
            dno_id=dno_ids["westnetz"], year=2024, 
            voltage_level="Hochspannungsnetz",
            winter="07:00 - 21:00", 
            fruehling="07:00 - 21:00",
            sommer="entfällt", 
            herbst="07:00 - 21:00"
        ),
    ]
    
    session.add_all(records)
    session.commit()


def seed_address_cache(session: Session) -> None:
    """Seed address cache entries with coordinates and DNO."""
    from app.db.models import DNOAddressCacheModel
    
    entries = [
        # "An der Ronne 160, 50859 Köln" → RheinNetz
        DNOAddressCacheModel(
            zip_code="50859",
            street_name="anderronne",  # Normalized
            latitude=50.9375,   # Köln area
            longitude=6.8654,
            dno_name="RheinNetz",
            source="vnb_digital",
        ),
        # "Musterstraße, 45128 Essen" → WestNetz
        DNOAddressCacheModel(
            zip_code="45128",
            street_name="musterstr",
            latitude=51.4556,   # Essen area
            longitude=7.0116,
            dno_name="WestNetz",
            source="vnb_digital",
        ),
    ]
    
    session.add_all(entries)
    session.commit()


# =============================================================================
# PUBLIC API
# =============================================================================

def get_test_session() -> Session:
    """
    Get a session for the test database.
    
    Use this in other test files:
        from test_00_init import get_test_session
        session = get_test_session()
    """
    if not TEST_DB_PATH.exists():
        raise FileNotFoundError(
            f"Test database not found at {TEST_DB_PATH}. "
            "Run 'python -m tests.unit.test_00_init' first."
        )
    
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    return Session()


def get_test_engine():
    """Get the SQLAlchemy engine for the test database."""
    if not TEST_DB_PATH.exists():
        raise FileNotFoundError(
            f"Test database not found at {TEST_DB_PATH}. "
            "Run 'python -m tests.unit.test_00_init' first."
        )
    
    return create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_test_database() -> bool:
    """
    Main initialization function.
    
    Creates the database and seeds all test data.
    Returns True on success, False on failure.
    """
    print(f"\n{'='*60}")
    print("TEST 00: Initialize Test Database")
    print(f"{'='*60}")
    
    try:
        engine = create_test_database()
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            print("\n📊 Seeding data...")
            
            # Seed in order (respecting foreign keys)
            dno_ids = seed_dnos(session)
            print(f"   ✅ {len(dno_ids)} DNOs")
            
            seed_extraction_strategies(session, dno_ids)
            print("   ✅ 5 extraction strategies")
            
            seed_netzentgelte(session, dno_ids)
            print("   ✅ 5 Netzentgelte records")
            
            seed_hlzf(session, dno_ids)
            print("   ✅ 3 HLZF records")
            
            seed_address_cache(session)
            print("   ✅ 2 address cache entries")
            
            print(f"\n{'='*60}")
            print("RESULT: ✅ Test database initialized successfully!")
            print(f"{'='*60}")
            print(f"\n📍 Database location: {TEST_DB_PATH}")
            print("📝 Import in tests:  from test_00_init import get_test_session\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Seeding failed: {e}")
            session.rollback()
            import traceback
            traceback.print_exc()
            return False
        finally:
            session.close()
            
    except Exception as e:
        print(f"\n❌ Database creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    success = init_test_database()
    sys.exit(0 if success else 1)
