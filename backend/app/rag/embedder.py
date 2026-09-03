from functools import lru_cache
import logging

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_fastembed():
    try:
        from fastembed import TextEmbedding

        logger.info("Initializing fastembed (ONNX runtime) for lightweight embedding...")
        return TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning(f"Fastembed unavailable or failed to initialize ({e}). Falling back to SentenceTransformer.")
        return None


@lru_cache(maxsize=1)
def _get_sentence_transformer():
    import torch

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from sentence_transformers import SentenceTransformer

    logger.info("Initializing SentenceTransformer PyTorch model...")
    return SentenceTransformer(settings.embedding_model, device="cpu")


def embed_texts(texts: list[str]) -> list[list[float]]:
    fe = _get_fastembed()
    if fe is not None:
        try:
            return [v.tolist() for v in fe.embed(texts)]
        except Exception as err:
            logger.warning(f"Fastembed encoding failed: {err}. Falling back to SentenceTransformer.")

    st = _get_sentence_transformer()
    import torch

    with torch.no_grad():
        vectors = st.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
