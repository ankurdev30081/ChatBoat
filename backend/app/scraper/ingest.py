"""Full ingestion pipeline: crawl -> chunk -> embed -> store.

Run as: python -m app.scraper.ingest
Optional: LIMIT_PER_SITE env var caps pages per site for a quick test run.
"""

import asyncio
import os
import uuid

from app.db import SessionLocal, init_db
from app.models import Document
from app.rag.embedder import embed_texts
from app.rag.vector_store import upsert_chunks
from app.scraper import darglobal, wasalt
from app.scraper.common import chunk_text

BATCH_SIZE = 64


def _process_and_store(site: str, pages: list[dict]) -> int:
    db = SessionLocal()
    total_chunks = 0
    try:
        batch_texts: list[str] = []
        batch_meta: list[dict] = []

        def flush():
            nonlocal total_chunks
            if not batch_texts:
                return
            vectors = embed_texts(batch_texts)
            points = []
            for text, meta, vector in zip(batch_texts, batch_meta, vectors):
                doc_id = str(uuid.uuid4())
                db.add(
                    Document(
                        id=doc_id,
                        site=site,
                        source_url=meta["source_url"],
                        chunk_index=meta["chunk_index"],
                        text=text,
                    )
                )
                points.append({"id": doc_id, "vector": vector, "text": text, "source_url": meta["source_url"], "site": site})
            upsert_chunks(points)
            db.commit()
            total_chunks += len(batch_texts)
            batch_texts.clear()
            batch_meta.clear()

        for page in pages:
            chunks = chunk_text(page["text"])
            for i, chunk in enumerate(chunks):
                batch_texts.append(chunk)
                batch_meta.append({"source_url": page["source_url"], "chunk_index": i})
                if len(batch_texts) >= BATCH_SIZE:
                    flush()
        flush()
    finally:
        db.close()
    return total_chunks


async def run() -> None:
    init_db()
    limit = os.getenv("LIMIT_PER_SITE")
    limit = int(limit) if limit else None

    print("Discovering DarGlobal URLs...")
    dar_urls = await darglobal.discover_urls(limit=limit)
    print(f"  found {len(dar_urls)} URLs")

    print("Discovering Wasalt URLs...")
    was_urls = await wasalt.discover_urls(limit_per_sitemap=limit)
    print(f"  found {len(was_urls)} URLs")

    print("Scraping DarGlobal (Playwright, may take a while)...")
    dar_pages = await darglobal.scrape_pages(dar_urls)
    print(f"  scraped {len(dar_pages)} pages")

    print("Scraping Wasalt...")
    was_pages = await wasalt.scrape_pages(was_urls)
    print(f"  scraped {len(was_pages)} pages")

    print("Embedding + storing DarGlobal chunks...")
    n1 = _process_and_store("darglobal", dar_pages)
    print(f"  stored {n1} chunks")

    print("Embedding + storing Wasalt chunks...")
    n2 = _process_and_store("wasalt", was_pages)
    print(f"  stored {n2} chunks")

    print(f"Done. Total chunks indexed: {n1 + n2}")


if __name__ == "__main__":
    asyncio.run(run())
