"""Wasalt scraper.

wasalt.sa is server-rendered (Next.js), but it sits behind Cloudflare bot
management which JS-challenges plain HTTP clients (httpx gets a 403 "Just a
moment..." page even though curl passes, due to TLS/JA3 fingerprinting) — so
page content is rendered with a real headless browser (Playwright), same as
DarGlobal. URL discovery uses the gzip sitemaps listed in robots.txt, which
are not behind the challenge. Only the English ("_en_") sitemaps are used to
avoid scraping duplicate Arabic/English content pairs; rental search result
pages (filter/listing pages, not real content) are skipped.
"""

import gzip
import re

import httpx

from app.scraper.common import BROWSER_USER_AGENT, browser_scrape_pages

SITE = "wasalt"

# Static/informational and rental-detail sitemaps are small and scraped in full.
# category (~6k) and especially product (~60k) are individual listing pages with
# highly repetitive templated content — scraping all of them would take many
# hours and mostly add near-duplicate text, so a representative sample is used
# instead. Override per-sitemap via `default_limit`/explicit caps below.
SITEMAPS: list[tuple[str, int | None]] = [
    ("https://cdn.wasalt.sa/sitemap/static_sitemap_en_sa.xml.gz", None),
    ("https://cdn.wasalt.sa/sitemap/rental_pdp_sitemap_en_sa.xml.gz", None),
    ("https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz", 150),
    ("https://cdn.wasalt.sa/sitemap/product_sitemap_en_sa.xml.gz", 300),
]


async def _fetch_sitemap_urls(client: httpx.AsyncClient, sitemap_url: str) -> list[str]:
    resp = await client.get(sitemap_url)
    resp.raise_for_status()
    raw = resp.content
    # httpx already decompresses a gzip Content-Encoding; the .gz file itself may
    # also be gzip-encoded content on top of that, so only decompress if needed.
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return re.findall(r"<loc>(.*?)</loc>", raw.decode("utf-8", errors="ignore"))


async def discover_urls(limit_per_sitemap: int | None = None) -> list[str]:
    """limit_per_sitemap, if given, overrides every sitemap's own default cap
    (used for quick smoke-test runs). Leave None to use the per-sitemap caps
    defined in SITEMAPS above."""
    urls: list[str] = []
    async with httpx.AsyncClient(headers={"User-Agent": BROWSER_USER_AGENT}, timeout=30) as client:
        for sitemap, default_cap in SITEMAPS:
            try:
                found = await _fetch_sitemap_urls(client, sitemap)
            except Exception as e:  # noqa: BLE001 - one bad sitemap shouldn't kill the run
                print(f"[wasalt] failed sitemap {sitemap}: {e}")
                continue
            cap = limit_per_sitemap if limit_per_sitemap is not None else default_cap
            if cap:
                found = found[:cap]
            urls.extend(found)
    return list(dict.fromkeys(urls))


async def scrape_pages(urls: list[str], concurrency: int = 4) -> list[dict]:
    return await browser_scrape_pages(urls, log_prefix=SITE, concurrency=concurrency, wait_ms=1200)
