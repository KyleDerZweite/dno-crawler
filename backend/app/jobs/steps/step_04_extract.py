"""
Step 04: Extract Data

Sends the downloaded file to a configurable AI model for intelligent extraction.

Supported providers:
- Gemini (Google) - gemini-2.0-flash, gemini-1.5-pro
- OpenAI - gpt-4o, gpt-4-turbo (vision)
- Anthropic - claude-3-5-sonnet (vision)
- Ollama (local) - llava, bakllava (for testing)

Configuration:
- AI_PROVIDER: "gemini" | "openai" | "anthropic" | "ollama"
- AI_MODEL: Model name (e.g., "gemini-2.0-flash")
- AI_API_KEY: API key for the provider

What it does:
- Load the file from local storage
- Upload to the configured AI provider with extraction prompt
- Parse the returned JSON into structured data
- Handle any format: PDF, Excel, Word, HTML, images

Output stored in job.context:
- extracted_data: list of records from extraction
- extraction_notes: any notes from AI about the source
- extraction_confidence: confidence score (0-1)
"""

import asyncio
from pathlib import Path
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlJobModel
from app.jobs.steps.base import BaseStep


class AIExtractor(ABC):
    """Base class for AI extraction providers."""
    
    @abstractmethod
    async def extract(
        self, 
        file_path: Path, 
        prompt: str
    ) -> dict:
        """Extract data from file using AI."""
        pass


class GeminiExtractor(AIExtractor):
    """Google Gemini API extractor."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
    
    async def extract(self, file_path: Path, prompt: str) -> dict:
        # TODO: Implement Gemini extraction
        # import google.generativeai as genai
        # genai.configure(api_key=self.api_key)
        # model = genai.GenerativeModel(self.model)
        # file = genai.upload_file(file_path)
        # response = await model.generate_content_async(
        #     [prompt, file],
        #     generation_config={"response_mime_type": "application/json"}
        # )
        # return json.loads(response.text)
        raise NotImplementedError("Gemini extractor not yet implemented")


class OpenAIExtractor(AIExtractor):
    """OpenAI API extractor (GPT-4 Vision)."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
    
    async def extract(self, file_path: Path, prompt: str) -> dict:
        # TODO: Implement OpenAI extraction
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI(api_key=self.api_key)
        # 
        # # For PDFs, need to convert to images first
        # # For images, encode as base64
        # 
        # response = await client.chat.completions.create(
        #     model=self.model,
        #     messages=[{"role": "user", "content": [...]}],
        #     response_format={"type": "json_object"}
        # )
        # return json.loads(response.choices[0].message.content)
        raise NotImplementedError("OpenAI extractor not yet implemented")


class AnthropicExtractor(AIExtractor):
    """Anthropic Claude API extractor."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
    
    async def extract(self, file_path: Path, prompt: str) -> dict:
        # TODO: Implement Anthropic extraction
        # from anthropic import AsyncAnthropic
        # client = AsyncAnthropic(api_key=self.api_key)
        # 
        # # Claude accepts PDFs directly (as of Claude 3.5)
        # 
        # response = await client.messages.create(
        #     model=self.model,
        #     messages=[{"role": "user", "content": [...]}]
        # )
        # return json.loads(response.content[0].text)
        raise NotImplementedError("Anthropic extractor not yet implemented")


class OllamaExtractor(AIExtractor):
    """Local Ollama extractor (for testing)."""
    
    def __init__(self, model: str = "llava", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
    
    async def extract(self, file_path: Path, prompt: str) -> dict:
        # TODO: Implement Ollama extraction
        # import ollama
        # 
        # # Ollama vision models work with images
        # # Need to convert PDF pages to images
        # 
        # response = await ollama.AsyncClient(host=self.host).chat(
        #     model=self.model,
        #     messages=[{"role": "user", "content": prompt, "images": [...]}]
        # )
        # return json.loads(response["message"]["content"])
        raise NotImplementedError("Ollama extractor not yet implemented")


def get_extractor(provider: str, model: str, api_key: str | None = None) -> AIExtractor:
    """Factory function to get the appropriate extractor."""
    match provider.lower():
        case "gemini":
            if not api_key:
                raise ValueError("Gemini requires an API key")
            return GeminiExtractor(api_key, model)
        case "openai":
            if not api_key:
                raise ValueError("OpenAI requires an API key")
            return OpenAIExtractor(api_key, model)
        case "anthropic":
            if not api_key:
                raise ValueError("Anthropic requires an API key")
            return AnthropicExtractor(api_key, model)
        case "ollama":
            return OllamaExtractor(model)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


class ExtractStep(BaseStep):
    label = "Extracting Data"
    description = "Using AI to extract structured data from document..."

    async def run(self, db: AsyncSession, job: CrawlJobModel) -> str:
        # TODO: Replace mock with actual implementation
        # Will use get_extractor() with config from settings or job context
        
        ctx = job.context or {}
        file_path = ctx.get("downloaded_file")
        file_format = ctx.get("file_format", "pdf")
        
        if not file_path:
            raise ValueError("No file to extract from")
        
        await asyncio.sleep(1.5)  # Simulate API call
        
        # TODO: Actual implementation:
        # from app.core.config import settings
        # 
        # extractor = get_extractor(
        #     provider=settings.ai_provider,  # e.g., "gemini"
        #     model=settings.ai_model,        # e.g., "gemini-2.0-flash"
        #     api_key=settings.ai_api_key,
        # )
        # 
        # prompt = self._build_prompt(ctx["dno_name"], job.year, job.data_type)
        # result = await extractor.extract(Path(file_path), prompt)
        
        # Mock: Return sample data
        if job.data_type == "netzentgelte":
            mock_data = [
                {"voltage_level": "Hochspannung", "arbeitspreis": 0.39, "leistungspreis": 210.29},
                {"voltage_level": "Umspannung HS/MS", "arbeitspreis": 0.39, "leistungspreis": 211.78},
                {"voltage_level": "Mittelspannung", "arbeitspreis": 1.33, "leistungspreis": 208.38},
                {"voltage_level": "Umspannung MS/NS", "arbeitspreis": 1.25, "leistungspreis": 195.07},
                {"voltage_level": "Niederspannung", "arbeitspreis": 1.68, "leistungspreis": 203.34},
            ]
        else:  # hlzf
            mock_data = [
                {"voltage_level": "Hochspannung", "winter": "08:00-12:00", "sommer": "entfällt"},
                {"voltage_level": "Mittelspannung", "winter": "08:00-12:00, 17:00-20:00", "sommer": "entfällt"},
                {"voltage_level": "Niederspannung", "winter": "08:00-20:00", "sommer": "10:00-14:00"},
            ]
        
        ctx["extracted_data"] = mock_data
        ctx["extraction_notes"] = f"Mock extraction from {file_format.upper()} document"
        ctx["extraction_confidence"] = 0.95
        ctx["extraction_provider"] = "mock"  # Will be actual provider name
        ctx["extraction_model"] = "mock"     # Will be actual model name
        await db.commit()
        
        return f"Extracted {len(mock_data)} records (confidence: 95%)"
    
    def _build_prompt(self, dno_name: str, year: int, data_type: str) -> str:
        """Build the extraction prompt (works for all providers)."""
        if data_type == "netzentgelte":
            return f"""
Extract Netzentgelte (network tariffs) data from this document.

DNO: {dno_name}
Year: {year}

For each voltage level, extract:
- voltage_level: Name as written (e.g., "Niederspannung", "Mittelspannung")
- arbeitspreis: Work price in ct/kWh
- leistungspreis: Capacity price in €/kW or €/kW/a

Return valid JSON:
{{
  "success": true,
  "data_type": "netzentgelte",
  "source_page": <page number>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "...", "arbeitspreis": ..., "leistungspreis": ...}}
  ]
}}
"""
        else:  # hlzf
            return f"""
Extract HLZF (Hochlastzeitfenster) data from this document.

DNO: {dno_name}
Year: {year}

For each voltage level, extract time windows per season:
- voltage_level: Name as written
- winter: Time window(s) or "entfällt"
- fruehling: Time window(s) or "entfällt"
- sommer: Time window(s) or "entfällt"
- herbst: Time window(s) or "entfällt"

Return valid JSON:
{{
  "success": true,
  "data_type": "hlzf",
  "source_page": <page number>,
  "notes": "<any observations>",
  "data": [
    {{"voltage_level": "...", "winter": "...", "sommer": "..."}}
  ]
}}
"""
