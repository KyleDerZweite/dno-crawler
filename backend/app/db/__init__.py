"""
Database package initialization.
"""

from app.db.database import (
    Base,
    DatabaseError,
    async_session_maker,
    close_db,
    engine,
    get_db,
    get_db_session,
    init_db,
)
from app.db.models import (
    AIProviderConfigModel,
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
    DNOBdewData,
    DNOMastrData,
    DNOVnbData,
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
    # Models - AI Provider
    "AIProviderConfigModel",
    # Models - Source Data
    "DNOMastrData",
    "DNOVnbData",
    "DNOBdewData",
]
