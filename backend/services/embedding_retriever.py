"""
embedding_retriever.py
Loads FAISS index + model once, provides embedding_search() for
sentences that regex retriever couldn't match.
"""

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
ROOT_DIR = os.path.dirname(BASE_DIR)  # project root
DATA_DIR = os.path.join(ROOT_DIR, "data")

INDEX_PATH = os.path.join(DATA_DIR, "kb_index.faiss")
METADATA_PATH = os.path.join(DATA_DIR, "kb_metadata.json")

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_index = None
_metadata = None


def _load():
    global _model, _index, _metadata
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    if _index is None:
        _index = faiss.read_index(INDEX_PATH)
    if _metadata is None:
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            _metadata = json.load(f)


def embedding_search(sentence, top_k=1, threshold=0.65):
    """
    Sentence ko embed karke FAISS index me top_k similar KB terms dhoondta hai.
    Returns list of dicts: {term, matched_text, similarity, match_type}
    """
    _load()

    if not sentence or not sentence.strip():
        return []

    vec = _model.encode([sentence], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(vec)

    scores, ids = _index.search(vec, top_k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1 or score < threshold:
            continue
        meta = _metadata[idx]
        results.append({
            "term": meta["term"],
            "matched_text": sentence.strip(),
            "simple_meaning": meta.get("simple_meaning"),
            "patient_explanation": meta.get("patient_explanation"),
            "body_system": meta.get("body_system"),
            "similarity": float(score),
            "match_type": "semantic",
        })

    return results