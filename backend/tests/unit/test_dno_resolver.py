"""
Unit tests for DNO Resolver service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.services.dno_resolver import DNOResolver


class TestDNOResolver:
    """Test DNO resolution service."""
    
    @pytest.fixture
    def resolver(self):
        """Create resolver without DB session."""
        return DNOResolver(db_session=None)
    
    @pytest.fixture
    def resolver_with_db(self):
        """Create resolver with mocked DB session."""
        mock_db = MagicMock()
        return DNOResolver(db_session=mock_db)
    
    # =========================================================================
    # Street Normalization Tests
    # =========================================================================
    
    def test_normalize_street_basic(self, resolver):
        """Test basic street normalization."""
        assert resolver.normalize_street("Hauptstraße") == "hauptstr"
        assert resolver.normalize_street("Hauptstrasse") == "hauptstr"
        assert resolver.normalize_street("Hauptstr.") == "hauptstr"
        assert resolver.normalize_street("Hauptstr") == "hauptstr"
    
    def test_normalize_street_with_spaces(self, resolver):
        """Test normalization removes spaces."""
        assert resolver.normalize_street("An der Ronne") == "anderronne"
        assert resolver.normalize_street("Am Alten Markt") == "amaltenmarkt"
    
    def test_normalize_street_case_insensitive(self, resolver):
        """Test normalization is case insensitive."""
        assert resolver.normalize_street("HAUPTSTRASSE") == "hauptstr"
        assert resolver.normalize_street("HauptStraße") == "hauptstr"
    
    # =========================================================================
    # Address Mapping Tests
    # =========================================================================
    
    def test_check_address_mapping_no_db(self, resolver):
        """Test cache check returns None without DB."""
        result = resolver.check_address_mapping("50859", "anderronne")
        assert result is None
    
    def test_save_address_mapping_no_db(self, resolver):
        """Test cache save does nothing without DB."""
        # Should not raise
        resolver.save_address_mapping("50859", "anderronne", "RheinNetz")
    
    def test_check_address_mapping_hit(self, resolver_with_db):
        """Test cache hit returns DNO name."""
        # Mock the cache entry
        mock_cache_entry = Mock()
        mock_cache_entry.dno_name = "RheinNetz"
        mock_cache_entry.hit_count = 5
        
        resolver_with_db.db.execute.return_value.scalar_one_or_none.return_value = mock_cache_entry
        
        result = resolver_with_db.check_address_mapping("50859", "anderronne")
        
        assert result == "RheinNetz"
        assert mock_cache_entry.hit_count == 6  # Incremented
    
    def test_check_address_mapping_miss(self, resolver_with_db):
        """Test cache miss returns None."""
        resolver_with_db.db.execute.return_value.scalar_one_or_none.return_value = None
        
        result = resolver_with_db.check_address_mapping("50859", "anderronne")
        
        assert result is None
    
    # =========================================================================
    # Resolution Tests
    # =========================================================================
    
    def test_resolve_with_cache_hit(self, resolver_with_db):
        """Test resolution returns cached result."""
        mock_cache_entry = Mock()
        mock_cache_entry.dno_name = "RheinNetz"
        mock_cache_entry.hit_count = 1
        
        resolver_with_db.db.execute.return_value.scalar_one_or_none.return_value = mock_cache_entry
        
        result = resolver_with_db.resolve("50859", "Köln", "An der Ronne")
        
        assert result == "RheinNetz"
    
    def test_resolve_without_services_returns_none(self, resolver):
        """Test resolution without search/LLM services returns None on cache miss."""
        result = resolver.resolve("50859", "Köln", "An der Ronne")
        assert result is None


class TestDNOResolverEdgeCases:
    """Edge case tests for DNO resolver."""
    
    @pytest.fixture
    def resolver(self):
        return DNOResolver(db_session=None)
    
    def test_normalize_empty_street(self, resolver):
        """Test normalizing empty street."""
        assert resolver.normalize_street("") == ""
    
    def test_normalize_street_special_chars(self, resolver):
        """Test normalization with numbers and special chars."""
        result = resolver.normalize_street("Musterstr. 123a")
        assert result == "musterstr123a"
