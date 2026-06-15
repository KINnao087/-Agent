from __future__ import annotations

import os
import threading
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DB_PATH = PROJECT_ROOT / "data" / "knowledge" / "db" / "chroma_db"
VECTOR_COUNTS = 5
SEARCH_RANKS = 5

_model_lock = threading.RLock()
_embedding_model = None
_cross_encoder = None
_chromadb_client = None
_chromadb_collection = None


def split2chunks(file_path: str | Path) -> list[str]:
    return [
        chunk
        for chunk in Path(file_path).read_text(encoding="utf-8").split("\n\n")
        if chunk.strip()
    ]


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer

                _embedding_model = SentenceTransformer(
                    os.getenv(
                        "RAG_EMBEDDING_MODEL",
                        "data/models/text2vec-base-chinese",
                    )
                )
    return _embedding_model


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        with _model_lock:
            if _cross_encoder is None:
                from sentence_transformers import CrossEncoder

                _cross_encoder = CrossEncoder(
                    os.getenv(
                        "RAG_RERANK_MODEL",
                        "data/models/mmarco-mMiniLMv2-L12-H384-v1",
                    )
                )
    return _cross_encoder


def _get_collection():
    global _chromadb_client, _chromadb_collection
    if _chromadb_collection is None:
        _chromadb_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        _chromadb_collection = _chromadb_client.get_or_create_collection("default")
    return _chromadb_collection


def embed_chunk(chunk: str) -> list[float]:
    return _get_embedding_model().encode(
        chunk,
        normalize_embeddings=True,
    ).tolist()


def save_embeddings(chunks: list[str], embeddings: list[list[float]]) -> None:
    _get_collection().upsert(
        documents=chunks,
        embeddings=embeddings,
        ids=[str(index) for index in range(len(chunks))],
    )


def retrieve(query: str, top_k: int = VECTOR_COUNTS) -> list[str]:
    result = _get_collection().query(
        query_embeddings=[embed_chunk(query)],
        n_results=top_k,
    )
    return result["documents"][0]


def rerank(
    query: str,
    chunks: list[str],
    top_k: int = SEARCH_RANKS,
) -> list[str]:
    scores = _get_cross_encoder().predict([(query, chunk) for chunk in chunks])
    ranked = sorted(zip(chunks, scores), key=lambda item: item[1], reverse=True)
    return [chunk for chunk, score in ranked if score >= -3.0][:top_k]


def get_and_rerank_chunks(
    query: str,
    get_top_k: int = VECTOR_COUNTS,
    rank_top_k: int = SEARCH_RANKS,
) -> list[str]:
    return rerank(query, retrieve(query, get_top_k), rank_top_k)


def format_chunks(chunks: list[str]) -> str:
    return "\n\n".join(
        f"[资料{index}]\n{chunk.strip()}"
        for index, chunk in enumerate(chunks, start=1)
        if chunk.strip()
    )
