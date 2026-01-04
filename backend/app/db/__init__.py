"""
Database package initialization.
"""

from app.db.database import Base, async_session_maker, close_db, engine, get_db, get_db_session, init_db, DatabaseError
from app.db.models import (
    CrawlJobModel,
    CrawlJobStepModel,
    DataSourceModel,
    DNOModel,
    DNOSourceProfile,
    HLZFModel,
    LocationModel,
    NetzentgelteModel,
    QueryLogModel,
    SystemLogModel,
)
from app.db.source_models import (
    DNOMastrData,
    DNOVnbData,
    DNOBdewData,
)

__all__ = [
    # Database
    "Base",
    "engine",
    "async_session_maker",
    "get_db",
    "get_db_session",
    "init_db",
    "close_db",
    "DatabaseError",
    # Models - Core
    "DNOModel",
    "LocationModel",
    "DNOSourceProfile",
    "NetzentgelteModel",
    "HLZFModel",
    "DataSourceModel",
    "CrawlJobModel",
    "CrawlJobStepModel",
    "QueryLogModel",
    "SystemLogModel",
    # Models - Source Data
    "DNOMastrData",
    "DNOVnbData",
    "DNOBdewData",
]
