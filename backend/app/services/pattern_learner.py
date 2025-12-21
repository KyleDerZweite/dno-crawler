"""
Pattern Learner Service for DNO Crawler.

Learns and applies URL patterns across DNOs to speed up crawling.
Patterns are stored with {year} placeholders for year-agnostic learning.

Key features:
- Year normalization: /2023/netzentgelte/ → /{year}/netzentgelte/
- Cross-DNO transfer: Patterns that work for RheinNetz are tried first on WestNetz
- Success rate tracking: High-success patterns are prioritized
"""

import re
from datetime import datetime
from urllib.parse import urlparse

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlPathPatternModel

logger = structlog.get_logger()


class PatternLearner:
    """Learns year-normalized URL patterns across DNOs."""
    
    # Regex to match 4-digit years in paths
    YEAR_PATTERN = re.compile(r'/(\d{4})/')
    
    # Path segments that are too generic to learn
    IGNORE_SEGMENTS = {"/", ""}
    
    def __init__(self):
        self.log = logger.bind(component="PatternLearner")
    
    async def get_priority_paths(
        self, 
        db: AsyncSession, 
        data_type: str,
        min_success_rate: float = 0.3,
        limit: int = 10,
    ) -> list[str]:
        """Get learned path patterns sorted by success rate.
        
        Args:
            db: Database session
            data_type: "netzentgelte" | "hlzf"
            min_success_rate: Minimum success rate to include (0.0-1.0)
            limit: Maximum number of patterns to return
            
        Returns:
            List of path patterns sorted by success rate (highest first)
        """
        # Query patterns that match data_type or "both"
        query = select(CrawlPathPatternModel).where(
            CrawlPathPatternModel.data_type.in_([data_type, "both"])
        ).order_by(
            desc(CrawlPathPatternModel.success_count)  # Most successful first
        ).limit(limit * 2)  # Get more than needed for filtering
        
        result = await db.execute(query)
        patterns = result.scalars().all()
        
        # Filter by success rate and return patterns
        filtered = [
            p.path_pattern for p in patterns 
            if p.success_rate >= min_success_rate
        ]
        
        self.log.debug(
            "Retrieved priority paths",
            data_type=data_type,
            total_patterns=len(patterns),
            filtered_count=len(filtered),
        )
        
        return filtered[:limit]
    
    def expand_pattern(self, pattern: str, year: int) -> str:
        """Expand {year} placeholder to actual year.
        
        Args:
            pattern: Pattern with {year} placeholder
            year: Year to substitute
            
        Returns:
            Pattern with year substituted
        """
        return pattern.replace("{year}", str(year))
    
    def _extract_path_patterns(self, url: str) -> list[str]:
        """Extract generalizable path patterns from URL.
        
        Normalizes years to {year} placeholder and generates
        parent path variations for learning.
        
        Args:
            url: Successful URL to learn from
            
        Returns:
            List of normalized path patterns
            
        Example:
            Input:  "https://dno.de/downloads/2023/strom/preisblatt.pdf"
            Output: [
                "/downloads/{year}/",
                "/downloads/{year}/strom/",
                "/downloads/",
                "/strom/",
            ]
        """
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Remove filename if present
            if "." in path.split("/")[-1]:
                path = "/".join(path.split("/")[:-1]) + "/"
            
            # Normalize years to {year}
            normalized = self.YEAR_PATTERN.sub("/{year}/", path)
            
            # Generate patterns from path segments
            patterns = set()
            
            # Full normalized path
            if normalized and normalized not in self.IGNORE_SEGMENTS:
                patterns.add(normalized)
            
            # Individual segments
            segments = [s for s in path.split("/") if s and not self.YEAR_PATTERN.match(f"/{s}/")]
            for segment in segments:
                pattern = f"/{segment}/"
                if pattern not in self.IGNORE_SEGMENTS:
                    patterns.add(pattern)
            
            # Partial paths (e.g., /downloads/{year}/, /veroeffentlichungen/netzentgelte/)
            parts = normalized.strip("/").split("/")
            for i in range(1, len(parts)):
                partial = "/" + "/".join(parts[:i]) + "/"
                if partial not in self.IGNORE_SEGMENTS:
                    patterns.add(partial)
            
            return list(patterns)
            
        except Exception as e:
            self.log.warning("Failed to extract patterns", url=url[:80], error=str(e))
            return []
    
    async def record_success(
        self,
        db: AsyncSession,
        url: str,
        dno_slug: str,
        data_type: str,
    ) -> list[str]:
        """Record successful URL and learn patterns from it.
        
        Args:
            db: Database session
            url: Successful URL
            dno_slug: DNO identifier
            data_type: "netzentgelte" | "hlzf"
            
        Returns:
            List of patterns that were updated/created
        """
        patterns = self._extract_path_patterns(url)
        updated_patterns = []
        
        for pattern in patterns:
            # Try to find existing pattern
            query = select(CrawlPathPatternModel).where(
                CrawlPathPatternModel.path_pattern == pattern
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing pattern
                existing.success_count += 1
                existing.last_success_at = datetime.utcnow()
                
                # Add DNO to successful list
                dno_list = existing.successful_dno_slugs or {"slugs": []}
                if dno_slug not in dno_list.get("slugs", []):
                    dno_list["slugs"] = dno_list.get("slugs", []) + [dno_slug]
                    existing.successful_dno_slugs = dno_list
                
                # Update data_type to "both" if it worked for different types
                if existing.data_type != "both" and existing.data_type != data_type:
                    existing.data_type = "both"
            else:
                # Create new pattern
                new_pattern = CrawlPathPatternModel(
                    path_pattern=pattern,
                    data_type=data_type,
                    success_count=1,
                    fail_count=0,
                    last_success_at=datetime.utcnow(),
                    successful_dno_slugs={"slugs": [dno_slug]},
                )
                db.add(new_pattern)
            
            updated_patterns.append(pattern)
        
        await db.flush()
        
        self.log.info(
            "Recorded success patterns",
            url=url[:60],
            dno=dno_slug,
            patterns_count=len(updated_patterns),
        )
        
        return updated_patterns
    
    async def record_failure(
        self,
        db: AsyncSession,
        pattern: str,
    ):
        """Increment fail count for a pattern that didn't work.
        
        Args:
            db: Database session
            pattern: Pattern that was tried and failed
        """
        query = select(CrawlPathPatternModel).where(
            CrawlPathPatternModel.path_pattern == pattern
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.fail_count += 1
            await db.flush()
            self.log.debug("Recorded pattern failure", pattern=pattern)


async def seed_initial_patterns(db: AsyncSession):
    """Seed database with common German DNO website patterns.
    
    Call this once during initial setup or migration.
    """
    patterns = [
        ("/downloads/", "both", 5),
        ("/service/", "both", 3),
        ("/netz/", "both", 3),
        ("/veroeffentlichungen/", "both", 5),
        ("/dokumente/", "both", 2),
        ("/downloads/{year}/", "both", 3),
        ("/netzentgelte/", "netzentgelte", 4),
        ("/preisblaetter/", "netzentgelte", 2),
        ("/netzzugang/", "both", 3),
        ("/netznutzung/", "both", 3),
        ("/strom/", "both", 2),
        ("/hochlastzeitfenster/", "hlzf", 3),
        ("/hlzf/", "hlzf", 2),
    ]
    
    for path_pattern, data_type, success_count in patterns:
        existing = await db.execute(
            select(CrawlPathPatternModel).where(
                CrawlPathPatternModel.path_pattern == path_pattern
            )
        )
        if not existing.scalar_one_or_none():
            db.add(CrawlPathPatternModel(
                path_pattern=path_pattern,
                data_type=data_type,
                success_count=success_count,
                fail_count=0,
            ))
    
    await db.flush()
    logger.info("Seeded initial path patterns")
