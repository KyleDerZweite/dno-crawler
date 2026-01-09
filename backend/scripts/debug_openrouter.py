import asyncio
import sys
from pathlib import Path

# Add backend to path so we can import app modules
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from openai import AsyncOpenAI

from app.core.config import settings


async def main():
    print("Checking OpenRouter configuration...")
    print(f"API URL: {settings.ai_api_url}")
    print(f"Model: {settings.ai_model}")

    if not settings.ai_api_key:
        print("Error: AI_API_KEY is not set")
        return

    # Initialize client with debug logging for httpx to see headers
    # We can't easily hook into internal httpx logger of openai client,
    # but we can verify the client configuration and make a request.

    headers = {
        "HTTP-Referer": "https://github.com/KyleDerZweite/dno-crawler",
        "X-Title": "DNO Crawler",
    }

    print(f"\nConfigured Headers: {headers}")

    client = AsyncOpenAI(
        base_url=settings.ai_api_url,
        api_key=settings.ai_api_key,
        default_headers=headers
    )

    print(f"\nSending test request to {settings.ai_model}...")

    try:
        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=[{
                "role": "user",
                "content": "Hello! Please reply with 'Headers received' if you can read this."
            }],
            max_tokens=20
        )

        print("\nSuccess! Response:")
        print(response.choices[0].message.content)
        print("\nThe request was successful, which means headers are likely accepted.")
        print("If headers were invalid, OpenRouter would usually ignore them or return a specific error.")

    except Exception as e:
        print(f"\nError occurred: {e}")
        # If it's an API status error, it might have more details
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")

if __name__ == "__main__":
    asyncio.run(main())
