"""
LLM Extractor service for AI-based data extraction.

Extracted from SearchAgent and crawl_job.py. Uses Ollama for fallback
extraction when regex-based methods fail.
"""

import re
import json
from pathlib import Path
from typing import Optional, Any

import ollama
import pdfplumber
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class LLMExtractor:
    """
    LLM-based data extraction using Ollama.
    
    Provides fallback extraction for Netzentgelte and HLZF data
    when regex-based extraction fails.
    """
    
    def __init__(self):
        """Initialize the LLM extractor."""
        self.log = logger.bind(component="LLMExtractor")
    
    def extract_dno_name(
        self, 
        search_results: list[dict], 
        zip_code: str
    ) -> Optional[str]:
        """
        DEPRECATED: Use VNBDigitalClient from app.services.vnb_digital instead.
        
        This method is no longer used. DNO name resolution is now handled by the
        VNB Digital GraphQL API which provides direct, reliable lookups.
        
        Use LLM to analyze search snippets and identify the DNO.
        
        Args:
            search_results: List of search result dicts with 'title', 'body'
            zip_code: Postal code being searched
            
        Returns:
            DNO name if identified, None otherwise
        """
        import warnings
        warnings.warn(
            "extract_dno_name is deprecated. Use VNBDigitalClient.resolve_address_to_dno() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if not search_results:
            return None
        
        snippets = "\n".join([
            f"- {r.get('title', '')}: {r.get('body', '')}" 
            for r in search_results
        ])
        
        prompt = f"""Analyze these search results for the German Grid Operator (Netzbetreiber) for ZIP {zip_code}.
Return ONLY the company name, nothing else. If unsure, return "UNKNOWN".

Results:
{snippets}"""
        
        response = self.call_ollama(prompt, model=settings.ollama_fast_model)
        
        if response and response.strip() != "UNKNOWN":
            # Clean up the response
            name = response.strip().strip('"').strip("'")
            # Remove any thinking or extra text
            if "\n" in name:
                name = name.split("\n")[0]
            # Basic validation - should be a reasonable company name
            if len(name) > 2 and len(name) < 100:
                return name
        
        return None
    
    def extract_netzentgelte(
        self, 
        pdf_path: Path, 
        dno_name: str, 
        year: int
    ) -> list[dict[str, Any]]:
        """
        Use LLM to extract Netzentgelte table from PDF.
        
        Args:
            pdf_path: Path to the PDF file
            dno_name: Name of the DNO
            year: Year of the data
            
        Returns:
            List of extracted Netzentgelte records
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Get text from first 5 pages
                text = "\n".join([
                    p.extract_text() or "" 
                    for p in pdf.pages[:5]
                ])
            
            prompt = f"""Extract the Netzentgelte (network charges) from this text for {dno_name} {year}.

Look for a table with voltage levels and prices:
- Voltage levels: Hochspannung, Umspannung HS/MS, Mittelspannung, Umspannung MS/NS, Niederspannung
- Price columns: Leistungspreis (€/kW), Arbeitspreis (ct/kWh)
- Some tables have 4 price columns: LP <2500h, AP <2500h, LP >=2500h, AP >=2500h

Return ONLY valid JSON, no explanation:
{{"records": [{{"voltage_level": "...", "leistung": ..., "arbeit": ..., "leistung_unter_2500h": ..., "arbeit_unter_2500h": ...}}]}}

Text:
{text[:4000]}"""
            
            response = self.call_ollama(prompt, model=settings.ollama_model)
            
            if response:
                # Try to parse JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    records = data.get("records", [])
                    self.log.info("LLM extraction succeeded", records=len(records))
                    return records
                    
        except json.JSONDecodeError as e:
            self.log.warning("Failed to parse LLM JSON response", error=str(e))
        except Exception as e:
            self.log.error("LLM table extraction failed", error=str(e))
        
        return []
    
    def extract_hlzf(
        self, 
        pdf_path: Path, 
        dno_name: str, 
        year: int
    ) -> list[dict[str, Any]]:
        """
        Use LLM to extract HLZF (Hochlastzeitfenster) data from PDF.
        
        Args:
            pdf_path: Path to the Regelungen PDF file
            dno_name: Name of the DNO
            year: Year of the data
            
        Returns:
            List of extracted HLZF records
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Find HLZF section
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if "hochlast" in page_text.lower():
                        text += page_text + "\n"
                
                if not text:
                    text = "\n".join([p.extract_text() or "" for p in pdf.pages[10:15]])
            
            prompt = f"""Extract the Hochlastzeitfenster (HLZF - peak load time windows) from this text for {dno_name} {year}.

Look for a table with:
- Rows: Voltage levels (Hochspannungsnetz, Umspannung zur Mittelspannung, Mittelspannungsnetz, etc.)
- Columns: Seasons (Winter, Frühling, Sommer, Herbst)
- Values: Time windows like "07:30-15:30" or "entfällt" (means null)

Return JSON only:
{{"records": [{{"voltage_level": "...", "winter": "...", "fruehling": null, "sommer": null, "herbst": "..."}}]}}

Text:
{text[:4000]}"""
            
            response = self.call_ollama(prompt, model=settings.ollama_model)
            
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    records = data.get("records", [])
                    self.log.info("LLM HLZF extraction succeeded", records=len(records))
                    return records
                    
        except json.JSONDecodeError as e:
            self.log.warning("Failed to parse LLM HLZF JSON response", error=str(e))
        except Exception as e:
            self.log.error("LLM HLZF extraction failed", error=str(e))
        
        return []
    
    def call_ollama(
        self, 
        prompt: str, 
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Call Ollama using the official Python module.
        
        Args:
            prompt: The prompt to send to the model
            model: Model name (defaults to settings.ollama_model)
            
        Returns:
            Model response text, or None if failed
        """
        model = model or settings.ollama_model
        
        try:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={
                    "temperature": 0.1,  # Low temperature for consistent output
                    "num_predict": 512,  # Limit output length
                }
            )
            
            return response.get("response", "")
            
        except Exception as e:
            self.log.error("Ollama call failed", error=str(e), model=model)
        
        return None


# Async version for use in async jobs
async def extract_with_ollama_async(
    netzentgelte_path: Optional[str],
    regelungen_path: Optional[str],
    dno_name: str,
    year: int,
) -> dict[str, list]:
    """
    Async version of LLM extraction for use in async jobs.
    
    Uses ollama.AsyncClient for async operations.
    
    Args:
        netzentgelte_path: Path to Netzentgelte PDF (if extraction needed)
        regelungen_path: Path to Regelungen PDF (if extraction needed)
        dno_name: Name of the DNO
        year: Year to extract data for
        
    Returns:
        Dict with "netzentgelte" and/or "hlzf" lists
    """
    log = logger.bind(dno=dno_name, year=year)
    results: dict[str, list] = {"netzentgelte": [], "hlzf": []}
    
    model = settings.ollama_model
    
    try:
        # Check if Ollama is available
        models = ollama.list()
        if not models:
            log.warning("No Ollama models available")
            return results
    except Exception as e:
        log.warning(f"Ollama connection failed: {e}")
        return results
    
    # Extract Netzentgelte with AI
    if netzentgelte_path:
        pdf_path = Path(netzentgelte_path)
        if pdf_path.exists():
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    text = "\n".join([p.extract_text() or "" for p in pdf.pages[:5]])
                
                prompt = f"""Extract the Netzentgelte (network charges) data from this text for {dno_name} {year}.

Look for a table with voltage levels (Hochspannung, Umspannung HS/MS, Mittelspannung, Umspannung MS/NS, Niederspannung) and 4 price columns:
1. Leistungspreis < 2500h
2. Arbeitspreis < 2500h  
3. Leistungspreis >= 2500h
4. Arbeitspreis >= 2500h

Return JSON only, no other text:
{{"records": [{{"voltage_level": "...", "lp_unter": ..., "ap_unter": ..., "lp": ..., "ap": ...}}]}}

Text:
{text[:4000]}"""

                response = ollama.generate(
                    model=model,
                    prompt=prompt,
                    options={"temperature": 0.1, "num_predict": 512}
                )
                
                answer = response.get("response", "")
                
                try:
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        for r in data.get("records", []):
                            results["netzentgelte"].append({
                                "voltage_level": r.get("voltage_level", ""),
                                "leistung_unter_2500h": r.get("lp_unter"),
                                "arbeit_unter_2500h": r.get("ap_unter"),
                                "leistung": r.get("lp"),
                                "arbeit": r.get("ap"),
                            })
                        log.info(f"AI extracted {len(results['netzentgelte'])} Netzentgelte records")
                except json.JSONDecodeError:
                    log.warning("Failed to parse AI response as JSON")
                        
            except Exception as e:
                log.error(f"AI Netzentgelte extraction failed: {e}")
    
    # Extract HLZF with AI
    if regelungen_path:
        pdf_path = Path(regelungen_path)
        if pdf_path.exists():
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if "hochlast" in page_text.lower():
                            text += page_text + "\n"
                    
                    if not text:
                        text = "\n".join([p.extract_text() or "" for p in pdf.pages[10:15]])
                
                prompt = f"""Extract the Hochlastzeitfenster (HLZF - peak load time windows) from this text for {dno_name} {year}.

Look for a table with:
- Rows: Voltage levels (Hochspannungsnetz, Umspannung zur Mittelspannung, Mittelspannungsnetz, etc.)
- Columns: Seasons (Winter, Frühling, Sommer, Herbst)
- Values: Time windows like "07:30-15:30" or "entfällt" (means null)

Return JSON only:
{{"records": [{{"voltage_level": "...", "winter": "...", "fruehling": null, "sommer": null, "herbst": "..."}}]}}

Text:
{text[:4000]}"""

                response = ollama.generate(
                    model=model,
                    prompt=prompt,
                    options={"temperature": 0.1, "num_predict": 512}
                )
                
                answer = response.get("response", "")
                
                try:
                    json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        for r in data.get("records", []):
                            results["hlzf"].append({
                                "voltage_level": r.get("voltage_level", ""),
                                "winter": r.get("winter"),
                                "fruehling": r.get("fruehling"),
                                "sommer": r.get("sommer"),
                                "herbst": r.get("herbst"),
                            })
                        log.info(f"AI extracted {len(results['hlzf'])} HLZF records")
                except json.JSONDecodeError:
                    log.warning("Failed to parse AI HLZF response as JSON")
                        
            except Exception as e:
                log.error(f"AI HLZF extraction failed: {e}")
    
    return results
