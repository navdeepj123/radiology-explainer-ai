"""
kb_indexer.py
One-time script: knowledge_base.json -> embeddings -> FAISS index.
Run: python data/kb_indexer.py
Output: data/kb_index.faiss, data/kb_metadata.json
"""

import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.json")
INDEX_PATH = os.path.join(BASE_DIR, "kb_index.faiss")
METADATA_PATH = os.path.join(BASE_DIR, "kb_metadata.json")

MODEL_NAME = "all-MiniLM-L6-v2"


def build_text(term_entry):
    """Term + definition + explanation ko ek text mein combine karta hai embedding ke liye."""
    parts = [
        term_entry.get("term", ""),
        term_entry.get("simple_meaning", ""),
        term_entry.get("patient_explanation", ""),
        term_entry.get("clinical_context", ""),
    ]
    parts += term_entry.get("related_terms", [])
    parts += term_entry.get("synonyms_in_report", [])
    return ". ".join(p for p in parts if p)


def main():
    print(f"Loading knowledge base from {KB_PATH} ...")
    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb_terms = json.load(f)

    print(f"Loaded {len(kb_terms)} terms.")

    print(f"Loading embedding model: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    texts = [build_text(t) for t in kb_terms]

    print("Encoding terms ...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    # Normalize for cosine similarity via inner product
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    print(f"Saving FAISS index to {INDEX_PATH} ...")
    faiss.write_index(index, INDEX_PATH)

    metadata = []
    for i, term_entry in enumerate(kb_terms):
        metadata.append({
            "faiss_id": i,
            "id": term_entry.get("id"),
            "term": term_entry.get("term"),
            "simple_meaning": term_entry.get("simple_meaning"),
            "patient_explanation": term_entry.get("patient_explanation"),
            "body_system": term_entry.get("body_system"),
            "category": term_entry.get("category"),
            "text_used": texts[i],
        })

    print(f"Saving metadata to {METADATA_PATH} ...")
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("Done. Index ready.")


if __name__ == "__main__":
    main()