from __future__ import annotations
import argparse, json
from pathlib import Path
from ponyguard_viqa.core import load_config, read_jsonl, write_jsonl
from ponyguard_viqa.evaluation import metrics
from ponyguard_viqa.llm import LocalLLM
from ponyguard_viqa.pipelines import PonyGuard
from ponyguard_viqa.retrieval import Embedder, Retriever

VARIANTS = {"full": {}, "minus_requirement": {"requirement": False}, "minus_inference": {"inference": False}, "minus_verification": {"verification": False}}

def main():
    p = argparse.ArgumentParser(); p.add_argument("--input", default="data/benchmark/test.jsonl"); p.add_argument("--limit", type=int); p.add_argument("--mock", action="store_true"); args = p.parse_args()
    c = load_config("configs/ponyguard.yaml"); r, m = c["retrieval"], c["model"]
    retriever = Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"]))
    rows = read_jsonl(args.input)[:args.limit]
    result = {}
    for name, enabled in VARIANTS.items():
        pipeline = PonyGuard(retriever, LocalLLM(m["name"], "mock" if args.mock else m["backend"], m["max_tokens"]), r["top_k"], enabled)
        predictions = [pipeline.run(row) for row in rows]; write_jsonl(f"runs/ablations/{name}.jsonl", predictions); result[name] = metrics(predictions)
    Path("reports/ablation.json").write_text(json.dumps(result, indent=2)); print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
