
import asyncio
import httpx
from app.services.robots_parser import fetch_and_verify_robots
import structlog

# Configure structured logging for the test
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
)

async def test_westnetz():
    async with httpx.AsyncClient(
        headers={"User-Agent": "DNO-Crawler/1.0 (robots check)"},
        follow_redirects=True,
    ) as client:
        website = "https://www.westnetz.de"
        print(f"Checking {website}...")
        result = await fetch_and_verify_robots(client, website, verify_sitemap=True)
        print("\nResult:")
        print(f"Crawlable: {result.crawlable}")
        print(f"Blocked Reason: {result.blocked_reason}")
        print(f"Sitemap Verified: {result.sitemap_verified}")
        print(f"Sitemap URLs: {result.sitemap_urls}")
        if result.raw_content:
            print(f"Content (first 100 chars): {result.raw_content[:100]}")
        else:
            print("No content")

if __name__ == "__main__":
    asyncio.run(test_westnetz())

