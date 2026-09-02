from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings

@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def ensure_collection() -> None:
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(size=settings.embedding_dim, distance=qmodels.Distance.COSINE),
        )


def upsert_chunks(points: list[dict]) -> None:
    """points: [{id, vector, text, source_url, site}]"""
    client = get_client()
    ensure_collection()
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            qmodels.PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload={"text": p["text"], "source_url": p["source_url"], "site": p["site"]},
            )
            for p in points
        ],
    )


def search(vector: list[float], top_k: int = 4) -> list[dict]:
    client = get_client()
    ensure_collection()
    hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=top_k,
    ).points
    return [
        {"text": h.payload.get("text", ""), "source_url": h.payload.get("source_url", ""), "score": h.score}
        for h in hits
    ]
