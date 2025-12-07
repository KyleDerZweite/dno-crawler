"""
Database package initialization.
"""

from app.db.database import Base, async_session_maker, close_db, engine, get_db, get_db_session, init_db, DatabaseError
from app.db.models import (
    APIKeyModel,
    CrawlAttemptModel,
    CrawlJobModel,
    CrawlJobStepModel,
    DataSourceModel,
    DNOCrawlConfigModel,
    DNOModel,
    ExtractionStrategyModel,
    HLZFModel,
    NetzentgelteModel,
    QueryLogModel,
    SessionModel,
    StrategyInsightModel,
    SystemLogModel,
    UserModel,
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
    # Models
    "DNOModel",
    "DNOCrawlConfigModel",
    "NetzentgelteModel",
    "HLZFModel",
    "DataSourceModel",
    "UserModel",
    "SessionModel",
    "APIKeyModel",
    "CrawlJobModel",
    "CrawlJobStepModel",
    "ExtractionStrategyModel",
    "CrawlAttemptModel",
    "StrategyInsightModel",
    "QueryLogModel",
    "SystemLogModel",
]
