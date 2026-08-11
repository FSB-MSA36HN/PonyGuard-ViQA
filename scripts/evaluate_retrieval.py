import json
from pathlib import Path
from ponyguard_viqa.core import load_config, read_jsonl
from ponyguard_viqa.retrieval import Embedder, Retriever, retrieval_metrics

def main():
    c = load_config("configs/base.yaml"); r = c["retrieval"]
    retriever = Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"]))
    result = retrieval_metrics(read_jsonl("data/benchmark/validation.jsonl"), retriever)
    Path("reports/retrieval_validation.json").write_text(json.dumps(result, indent=2)); print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
