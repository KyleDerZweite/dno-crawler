"""
DNO Resolver service for address → DNO name resolution.

Extracted from SearchAgent. Uses cache + web search + LLM.
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
    1. Check database cache for known address → DNO mappings
    2. Web search via SearchEngine to find DNO candidates
    3. LLM extraction to identify DNO name from search results
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the DNO resolver.
        
        Args:
            db_session: Optional database session for caching
        """
        self.db = db_session
        self.log = logger.bind(component="DNOResolver")
    
    def resolve(
        self, 
        zip_code: str, 
        city: str, 
        street: str,
        search_engine: Optional["SearchEngine"] = None,
        llm_extractor: Optional["LLMExtractor"] = None,
    ) -> Optional[str]:
        """
        Determine the DNO name from an address.
        
        Args:
            zip_code: German postal code (PLZ)
            city: City name
            street: Street name
            search_engine: Optional SearchEngine instance for web search
            llm_extractor: Optional LLMExtractor instance for result analysis
            
        Returns:
            DNO name if found, None otherwise
        """
        log = self.log.bind(zip_code=zip_code, city=city)
        
        # 1. Normalize & Check Cache
        norm_street = self.normalize_street(street)
        cached = self.check_cache(zip_code, norm_street)
        if cached:
            log.info("Cache hit", dno=cached)
            return cached
        
        # 2. If we have a search engine, perform web search
        if search_engine and llm_extractor:
            query = f"Netzbetreiber Strom {zip_code} {city} {street}"
            log.info("Searching external", query=query)
            
            results = search_engine.safe_search(query)
            if not results:
                log.warning("No search results found")
                return None
            
            # 3. LLM extraction
            dno_name = llm_extractor.extract_dno_name(results, zip_code)
            if dno_name:
                self.save_to_cache(zip_code, norm_street, dno_name)
                log.info("DNO resolved", dno=dno_name)
                return dno_name
            
            log.warning("Could not extract DNO from results")
        
        return None
    
    def normalize_street(self, street: str) -> str:
        """Normalize street name for cache key."""
        return (
            street.lower()
            .replace("straße", "str")
            .replace("strasse", "str")
            .replace("str.", "str")
            .replace(" ", "")
        )
    
    def check_cache(self, zip_code: str, norm_street: str) -> Optional[str]:
        """Check DB cache for existing DNO mapping."""
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
            self.log.warning("Cache lookup failed", error=str(e))
        
        return None
    
    def save_to_cache(
        self, 
        zip_code: str, 
        norm_street: str, 
        dno_name: str,
        confidence: float = 0.9
    ) -> None:
        """Save DNO mapping to cache."""
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
            self.log.info("Saved to cache", zip=zip_code, dno=dno_name)
            
        except Exception as e:
            self.log.warning("Cache save failed", error=str(e))
            try:
                self.db.rollback()
            except:
                pass
