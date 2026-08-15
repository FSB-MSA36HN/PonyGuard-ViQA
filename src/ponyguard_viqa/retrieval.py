from __future__ import annotations

import json
import os
from time import perf_counter
from pathlib import Path
from typing import Any

# faiss-cpu and PyTorch ship separate OpenMP copies on macOS; set before either loads.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np

from .core import Chunk, normalize_text


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = normalize_text(text).split()
    if not words: return []
    step = max(1, size - overlap)
    return [" ".join(words[start:start + size]) for start in range(0, len(words), step)]


class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def encode(self, values: list[str], query: bool = False) -> np.ndarray:
        from sentence_transformers import SentenceTransformer
        if self._model is None: self._model = SentenceTransformer(self.model_name, local_files_only=True)
        prefix = "query: " if query else "passage: "
        return self._model.encode([prefix + value for value in values], normalize_embeddings=True, show_progress_bar=False).astype("float32")


class Retriever:
    def __init__(self, index_path: str | Path, documents_path: str | Path, embedder: Embedder):
        self.index_path = str(index_path)
        self.index = None
        self.documents = [json.loads(line) for line in Path(documents_path).open(encoding="utf-8") if line.strip()]
        self.embedder = embedder
        self.last_timing: dict[str, float] = {}

    def retrieve(self, question: str, top_k: int = 5) -> list[Chunk]:
        started = perf_counter()
        # Embeddings should not change retrieval solely because a user capitalized a word.
        vector = self.embedder.encode([normalize_text(question).casefold()], query=True)
        embedded = perf_counter()
        # Import FAISS after Torch/SentenceTransformers on macOS to avoid their OpenMP loader conflict.
        if self.index is None:
            import faiss
            self.index = faiss.read_index(self.index_path)
        loaded = perf_counter()
        scores, ids = self.index.search(vector, top_k)
        finished = perf_counter()
        self.last_timing = {"embedding_ms": round((embedded-started)*1000, 2), "index_load_ms": round((loaded-embedded)*1000, 2), "faiss_search_ms": round((finished-loaded)*1000, 2), "total_ms": round((finished-started)*1000, 2)}
        return [Chunk(document_id=self.documents[index]["document_id"], chunk_id=self.documents[index]["chunk_id"], text=self.documents[index]["text"], score=float(score)) for score, index in zip(scores[0], ids[0]) if index >= 0]


def build_index(corpus: list[dict[str, Any]], output_dir: str | Path, embedder: Embedder, size: int, overlap: int) -> dict[str, Any]:
    import faiss
    docs = []
    for source in corpus:
        for number, text in enumerate(chunk_text(source["text"], size, overlap), 1):
            docs.append({"document_id": source["document_id"], "chunk_id": f"{source['document_id']}_chunk_{number:06d}", "text": text, "source_context": source["text"]})
    if not docs: raise ValueError("Corpus has no chunks")
    vectors = embedder.encode([doc["text"] for doc in docs])
    index = faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors)
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_dir / "faiss.index"))
    with (output_dir / "documents.jsonl").open("w", encoding="utf-8") as handle:
        for doc in docs: handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    metadata = {"embedding_model": embedder.model_name, "chunk_size": size, "chunk_overlap": overlap, "chunks": len(docs)}
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def retrieval_metrics(rows: list[dict[str, Any]], retriever: Retriever, top_ks=(1, 3, 5, 10)) -> dict[str, float]:
    hits = {k: 0 for k in top_ks}; reciprocal = []
    for row in rows:
        if not row["is_answerable"]: continue
        chunk_list = retriever.retrieve(row["question"], max(top_ks))
        ranked = [chunk.document_id for chunk in chunk_list]
        # Corpus document is recoverable via exact normalized source context.
        target = next((doc["document_id"] for doc in retriever.documents if normalize_text(row["context"]) == normalize_text(doc.get("source_context", ""))), None)
        rank = ranked.index(target) + 1 if target in ranked else None
        reciprocal.append(1 / rank if rank else 0)
        for k in top_ks: hits[k] += int(bool(rank and rank <= k))
    count = max(1, len(reciprocal))
    return {**{f"recall@{k}": hits[k] / count for k in top_ks}, "mrr": sum(reciprocal) / count}
