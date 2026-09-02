from app.rag.embedder import embed_query
from app.rag.vector_store import search


def retrieve_context(query: str, top_k: int = 4) -> tuple[str, list[str]]:
    vector = embed_query(query)
    hits = search(vector, top_k=top_k)
    if not hits:
        return "", []

    blocks = []
    sources = []
    for h in hits:
        blocks.append(f"[Source: {h['source_url']}]\n{h['text']}")
        sources.append(h["source_url"])
    return "\n\n---\n\n".join(blocks), list(dict.fromkeys(sources))
