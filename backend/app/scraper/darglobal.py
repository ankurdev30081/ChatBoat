"""DarGlobal scraper.

darglobal.co.uk sits behind Incapsula bot protection: plain HTTP requests to
any content page return an empty JS-challenge shell, so page content must be
rendered with a real browser (Playwright). The sitemap.xml endpoint itself is
not protected and is used purely for URL discovery.
"""

import httpx

from app.scraper.common import BROWSER_USER_AGENT, browser_scrape_pages

SITE = "darglobal"
SITEMAP_URL = "https://darglobal.co.uk/sitemap.xml"

# robots.txt disallows these query params / paths — never fetch URLs containing them.
_DISALLOWED_SUBSTRINGS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "sfmc_activityid", "sfmc_journey_id", "sfmc_journey_name", "dealercode", "ltclid",
    "wc-ajax", "post_type", "?s=", "&s=", "menu-bwvsd", "tp_sp", "trk=", "#trk",
]


def _is_allowed(url: str) -> bool:
    return not any(s in url for s in _DISALLOWED_SUBSTRINGS)


async def discover_urls(limit: int | None = None) -> list[str]:
    async with httpx.AsyncClient(headers={"User-Agent": BROWSER_USER_AGENT}, timeout=30) as client:
        resp = await client.get(SITEMAP_URL)
        resp.raise_for_status()

    import re

    urls = re.findall(r"<loc>(.*?)</loc>", resp.text)
    urls = [u.strip() for u in urls if _is_allowed(u.strip())]
    urls = list(dict.fromkeys(urls))  # dedupe, preserve order
    return urls[:limit] if limit else urls


async def scrape_pages(urls: list[str], concurrency: int = 3) -> list[dict]:
    """Returns [{source_url, text}] for pages that rendered successfully."""
    return await browser_scrape_pages(urls, log_prefix=SITE, concurrency=concurrency, wait_ms=2500)
