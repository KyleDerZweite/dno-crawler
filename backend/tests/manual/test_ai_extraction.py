#!/usr/bin/env python
"""
Manual test script for AI extraction debugging.

Usage:
    cd /home/kyle/CodingProjects/dno-crawler/backend
    python -m tests.manual.test_ai_extraction

Tests the AI extractor on HTML and PDF files to diagnose extraction issues.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env file BEFORE importing app modules
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded .env from: {env_file}")
else:
    print(f"⚠️  No .env file found at: {env_file}")


async def test_text_extraction():
    """Test AI extraction on HTML file."""
    from app.services.extraction.ai_extractor import get_ai_extractor
    from app.core.config import settings
    
    print("\n" + "=" * 60)
    print("AI EXTRACTION TEST - TEXT MODE (HTML)")
    print("=" * 60)
    
    print(f"\n📋 Configuration:")
    print(f"   AI_API_URL: {settings.ai_api_url}")
    print(f"   AI_MODEL:   {settings.ai_model}")
    print(f"   AI_ENABLED: {settings.ai_enabled}")
    
    if not settings.ai_enabled:
        print("\n❌ AI is not enabled. Set AI_API_URL and AI_MODEL in .env")
        return
    
    # Test file
    test_file = Path("/home/kyle/CodingProjects/dno-crawler/data/downloads/rheinnetz-gmbh-rng/rheinnetz-gmbh-rng-hlzf-2024.html")
    
    if not test_file.exists():
        print(f"\n❌ Test file not found: {test_file}")
        return
    
    print(f"\n📄 Test file: {test_file.name}")
    print(f"   Size: {test_file.stat().st_size} bytes")
    
    # Read content
    content = test_file.read_text(encoding="utf-8", errors="replace")
    print(f"   Content length: {len(content)} chars")
    
    # Build prompt
    prompt = """Extract HLZF (Hochlastzeitfenster) data from this HTML content.

For each voltage level (row in the table), extract:
- voltage_level: Name as written (e.g., "HS", "HS/MS", "MS", "MS/NS", "NS")
- winter: Time window(s) for winter season
- fruehling: Time window(s) for spring (Frühjahr)
- sommer: Time window(s) for summer
- herbst: Time window(s) for autumn

Return valid JSON:
{
  "success": true,
  "data_type": "hlzf",
  "notes": "<any observations>",
  "data": [
    {"voltage_level": "...", "winter": "...", "fruehling": "...", "sommer": "...", "herbst": "..."}
  ]
}
"""
    
    print("\n🚀 Starting extraction...")
    
    try:
        extractor = get_ai_extractor()
        if extractor is None:
            print("❌ Could not create extractor (AI not configured)")
            return
            
        result = await extractor.extract_text(content, prompt)
        
        print("\n✅ Extraction successful!")
        print(f"\n📊 Result:")
        print(f"   Success: {result.get('success')}")
        print(f"   Notes: {result.get('notes', 'N/A')}")
        print(f"   Records: {len(result.get('data', []))}")
        
        for i, record in enumerate(result.get("data", []), 1):
            print(f"\n   [{i}] {record.get('voltage_level', 'Unknown')}")
            print(f"       Winter:    {record.get('winter', '-')}")
            print(f"       Frühjahr:  {record.get('fruehling', '-')}")
            print(f"       Sommer:    {record.get('sommer', '-')}")
            print(f"       Herbst:    {record.get('herbst', '-')}")
            
    except Exception as e:
        print(f"\n❌ Extraction failed!")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        
        import traceback
        print(f"\n📋 Full traceback:")
        traceback.print_exc()


async def main():
    print("\n" + "=" * 60)
    print("AI EXTRACTION DEBUG TOOL")
    print("=" * 60)
    
    await test_text_extraction()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
