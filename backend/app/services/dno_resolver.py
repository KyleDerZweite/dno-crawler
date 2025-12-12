"""
DNO Resolver service for address → DNO name caching.

Provides database caching layer for address → DNO mappings:
- check_address_mapping(): Lookup existing cached mapping
- save_address_mapping(): Store new mapping in cache
- normalize_street(): Normalize street names for cache keys

NOTE: Primary DNO resolution is handled by VNBDigitalClient (app.services.vnb_digital).
"""

import re
from typing import Optional

import structlog
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.config import settings

logger = structlog.get_logger()


class DNOResolver:
    """
    Resolve address to DNO (Distribution Network Operator) name.
    
    Uses a three-tier approach:
    1. Check database for known address → DNO mappings
    2. Web search via SearchEngine to find DNO candidates
    3. LLM extraction to identify DNO name from search results
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the DNO resolver.
        
        Args:
            db_session: Optional database session for address mappings
        """
        self.db = db_session
        self.log = logger.bind(component="DNOResolver")
    
    def normalize_street(self, street: str) -> str:
        """Normalize street name for cache key."""
        return (
            street.lower()
            .replace("straße", "str")
            .replace("strasse", "str")
            .replace("str.", "str")
            .replace(" ", "")
        )
    
    def check_address_mapping(self, zip_code: str, norm_street: str) -> Optional[str]:
        """Check database for existing address → DNO mapping."""
        if not self.db:
            return None
        
        try:
            from app.db.models import DNOAddressCacheModel
            
            query = select(DNOAddressCacheModel).where(
                and_(
                    DNOAddressCacheModel.zip_code == zip_code,
                    DNOAddressCacheModel.street_name == norm_street
                )
            )
            result = self.db.execute(query)
            cache_entry = result.scalar_one_or_none()
            
            if cache_entry:
                # Update hit count
                cache_entry.hit_count += 1
                self.db.commit()
                return cache_entry.dno_name
                
        except Exception as e:
            self.log.warning("Address mapping lookup failed", error=str(e))
        
        return None
    
    def save_address_mapping(
        self, 
        zip_code: str, 
        norm_street: str, 
        dno_name: str,
        confidence: float = 0.9
    ) -> None:
        """Save address → DNO mapping to database."""
        if not self.db:
            return
        
        try:
            from app.db.models import DNOAddressCacheModel
            
            # Check if entry already exists
            existing = self.db.execute(
                select(DNOAddressCacheModel).where(
                    and_(
                        DNOAddressCacheModel.zip_code == zip_code,
                        DNOAddressCacheModel.street_name == norm_street
                    )
                )
            ).scalar_one_or_none()
            
            if existing:
                # Update existing entry
                existing.dno_name = dno_name
                existing.confidence = confidence
                existing.hit_count += 1
            else:
                # Create new entry
                cache_entry = DNOAddressCacheModel(
                    zip_code=zip_code,
                    street_name=norm_street,
                    dno_name=dno_name,
                    confidence=confidence,
                    source="ddgs",
                    hit_count=1,
                )
                self.db.add(cache_entry)
            
            self.db.commit()
            self.log.info("Saved address mapping", zip=zip_code, dno=dno_name)
            
        except Exception as e:
            self.log.warning("Address mapping save failed", error=str(e))
            try:
                self.db.rollback()
            except:
                pass
