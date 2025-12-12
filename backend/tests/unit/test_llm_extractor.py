"""
Unit tests for LLM Extractor service.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.extraction.llm_extractor import LLMExtractor


class TestLLMExtractor:
    """Test LLM-based extraction service."""
    
    @pytest.fixture
    def extractor(self):
        """Create LLM extractor instance."""
        return LLMExtractor()
    
    # =========================================================================
    # DNO Name Extraction Tests
    # =========================================================================
    
    def test_extract_dno_name_empty_results(self, extractor):
        """Test extraction from empty results returns None."""
        result = extractor.extract_dno_name([], "50859")
        assert result is None
    
    @patch.object(LLMExtractor, 'call_ollama')
    def test_extract_dno_name_success(self, mock_ollama, extractor):
        """Test successful DNO name extraction."""
        mock_ollama.return_value = "RheinNetz"
        
        results = [
            {"title": "RheinNetz GmbH", "body": "Verteilnetzbetreiber Köln"},
            {"title": "Strom Köln", "body": "Energieversorgung"},
        ]
        
        dno = extractor.extract_dno_name(results, "50859")
        
        assert dno == "RheinNetz"
        mock_ollama.assert_called_once()
    
    @patch.object(LLMExtractor, 'call_ollama')
    def test_extract_dno_name_unknown(self, mock_ollama, extractor):
        """Test UNKNOWN response returns None."""
        mock_ollama.return_value = "UNKNOWN"
        
        results = [{"title": "Random", "body": "No DNO info"}]
        dno = extractor.extract_dno_name(results, "50859")
        
        assert dno is None
    
    @patch.object(LLMExtractor, 'call_ollama')
    def test_extract_dno_name_cleans_response(self, mock_ollama, extractor):
        """Test response is cleaned of quotes and extra text."""
        mock_ollama.return_value = '"RheinNetz GmbH"\n\nThis is the network operator.'
        
        results = [{"title": "RheinNetz", "body": "DNO"}]
        dno = extractor.extract_dno_name(results, "50859")
        
        assert dno == "RheinNetz GmbH"
    
    # =========================================================================
    # Ollama Call Tests
    # =========================================================================
    
    @patch('app.services.extraction.llm_extractor.ollama')
    def test_call_ollama_success(self, mock_ollama_module, extractor):
        """Test successful Ollama API call."""
        mock_ollama_module.generate.return_value = {"response": "Test response"}
        
        result = extractor.call_ollama("Test prompt")
        
        assert result == "Test response"
        mock_ollama_module.generate.assert_called_once()
    
    @patch('app.services.extraction.llm_extractor.ollama')
    def test_call_ollama_with_options(self, mock_ollama_module, extractor):
        """Test Ollama is called with correct options."""
        mock_ollama_module.generate.return_value = {"response": "Test"}
        
        extractor.call_ollama("Test prompt", model="test-model")
        
        call_kwargs = mock_ollama_module.generate.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert "options" in call_kwargs
        assert call_kwargs["options"]["temperature"] == 0.1
    
    @patch('app.services.extraction.llm_extractor.ollama')
    def test_call_ollama_exception(self, mock_ollama_module, extractor):
        """Test Ollama exception returns None."""
        mock_ollama_module.generate.side_effect = Exception("Connection refused")
        
        result = extractor.call_ollama("Test prompt")
        
        assert result is None
    
    @patch('app.services.extraction.llm_extractor.ollama')
    def test_call_ollama_empty_response(self, mock_ollama_module, extractor):
        """Test empty response is returned correctly."""
        mock_ollama_module.generate.return_value = {"response": ""}
        
        result = extractor.call_ollama("Test prompt")
        
        assert result == ""
    
    # =========================================================================
    # Netzentgelte Extraction Tests
    # =========================================================================
    
    @patch.object(LLMExtractor, 'call_ollama')
    @patch('app.services.extraction.llm_extractor.pdfplumber')
    def test_extract_netzentgelte_success(self, mock_pdfplumber, mock_ollama, extractor):
        """Test successful Netzentgelte extraction."""
        # Mock PDF reading
        mock_page = Mock()
        mock_page.extract_text.return_value = "Netzentgelte Preisblatt 2024"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        # Mock LLM response
        mock_ollama.return_value = json.dumps({
            "records": [
                {"voltage_level": "Hochspannung", "leistung": 230.0, "arbeit": 0.5}
            ]
        })
        
        result = extractor.extract_netzentgelte(Path("/fake/path.pdf"), "RheinNetz", 2024)
        
        assert len(result) == 1
        assert result[0]["voltage_level"] == "Hochspannung"
    
    @patch.object(LLMExtractor, 'call_ollama')
    @patch('app.services.extraction.llm_extractor.pdfplumber')
    def test_extract_netzentgelte_invalid_json(self, mock_pdfplumber, mock_ollama, extractor):
        """Test handling of invalid JSON response."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Some text"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        mock_ollama.return_value = "This is not valid JSON"
        
        result = extractor.extract_netzentgelte(Path("/fake/path.pdf"), "RheinNetz", 2024)
        
        assert result == []
    
    @patch.object(LLMExtractor, 'call_ollama')
    @patch('app.services.extraction.llm_extractor.pdfplumber')
    def test_extract_netzentgelte_ollama_fails(self, mock_pdfplumber, mock_ollama, extractor):
        """Test handling when Ollama returns None."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Some text"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        mock_ollama.return_value = None
        
        result = extractor.extract_netzentgelte(Path("/fake/path.pdf"), "RheinNetz", 2024)
        
        assert result == []
    
    # =========================================================================
    # HLZF Extraction Tests
    # =========================================================================
    
    @patch.object(LLMExtractor, 'call_ollama')
    @patch('app.services.extraction.llm_extractor.pdfplumber')
    def test_extract_hlzf_success(self, mock_pdfplumber, mock_ollama, extractor):
        """Test successful HLZF extraction."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hochlastzeitfenster Table"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        mock_ollama.return_value = json.dumps({
            "records": [
                {"voltage_level": "HS", "winter": "09:00-17:00", "fruehling": None}
            ]
        })
        
        result = extractor.extract_hlzf(Path("/fake/path.pdf"), "RheinNetz", 2024)
        
        assert len(result) == 1
        assert result[0]["voltage_level"] == "HS"
        assert result[0]["winter"] == "09:00-17:00"
    
    @patch.object(LLMExtractor, 'call_ollama')
    @patch('app.services.extraction.llm_extractor.pdfplumber')
    def test_extract_hlzf_finds_section(self, mock_pdfplumber, mock_ollama, extractor):
        """Test HLZF extraction finds the hochlast section."""
        # First page without hochlast
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Random content"
        
        # Second page with hochlast
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Hochlastzeitfenster table here"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        mock_ollama.return_value = json.dumps({"records": []})
        
        extractor.extract_hlzf(Path("/fake/path.pdf"), "RheinNetz", 2024)
        
        # Verify ollama was called
        mock_ollama.assert_called_once()
        call_prompt = mock_ollama.call_args[0][0]
        # The prompt should contain the hochlast page content
        assert "Hochlastzeitfenster" in call_prompt


class TestLLMExtractorPrompts:
    """Test prompt generation for LLM extractor."""
    
    @pytest.fixture
    def extractor(self):
        return LLMExtractor()
    
    @patch.object(LLMExtractor, 'call_ollama')
    def test_dno_prompt_includes_zip(self, mock_ollama, extractor):
        """Test DNO prompt includes ZIP code."""
        mock_ollama.return_value = "TestDNO"
        
        extractor.extract_dno_name([{"title": "Test", "body": "Test"}], "50859")
        
        call_args = mock_ollama.call_args[0][0]
        assert "50859" in call_args
    
    @patch.object(LLMExtractor, 'call_ollama')
    def test_dno_prompt_includes_snippets(self, mock_ollama, extractor):
        """Test DNO prompt includes search snippets."""
        mock_ollama.return_value = "TestDNO"
        
        extractor.extract_dno_name([
            {"title": "RheinNetz GmbH", "body": "Netzbetreiber Köln"}
        ], "50859")
        
        call_args = mock_ollama.call_args[0][0]
        assert "RheinNetz" in call_args
        assert "Netzbetreiber" in call_args
