import asyncio
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

CHUNK_SIZE = 1000  # chars
CHUNK_OVERLAP = 150

# Tags whose content is boilerplate, not article/page content.
_STRIP_TAGS = ["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    main = soup.find("main") or soup.body or soup
    text = main.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if len(chunk) > 50:  # skip near-empty tail chunks
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


async def browser_scrape_pages(
    urls: list[str],
    log_prefix: str,
    concurrency: int = 4,
    wait_ms: int = 1200,
    min_text_len: int = 200,
) -> list[dict]:
    """Fetch pages with a real headless browser, bypassing Cloudflare/Incapsula
    JS challenges that block plain HTTP clients. Returns [{source_url, text}]."""
    results: list[dict] = []
    sem = asyncio.Semaphore(concurrency)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=BROWSER_USER_AGENT)

        async def fetch_one(url: str):
            async with sem:
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(wait_ms)
                    html = await page.content()
                    text = html_to_text(html)
                    if text and len(text) > min_text_len:
                        results.append({"source_url": url, "text": text})
                except Exception as e:  # noqa: BLE001 - best-effort scraping
                    print(f"[{log_prefix}] failed {url}: {e}")
                finally:
                    await page.close()

        await asyncio.gather(*(fetch_one(u) for u in urls))
        await browser.close()

    return results
