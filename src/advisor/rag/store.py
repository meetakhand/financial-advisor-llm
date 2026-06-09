"""Chroma persistent client + collection accessors."""
from __future__ import annotations

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from advisor.config import settings

COLLECTION_NAME = "finance"


def get_embedder():
    return SentenceTransformerEmbeddingFunction(model_name=settings.embed_model_id)


def get_client() -> chromadb.PersistentClient:
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_path))


def get_or_create_collection():
    return get_client().get_or_create_collection(COLLECTION_NAME, embedding_function=get_embedder())


def get_collection():
    return get_client().get_collection(COLLECTION_NAME, embedding_function=get_embedder())
