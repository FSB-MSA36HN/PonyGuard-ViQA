from __future__ import annotations
import argparse, json
from pathlib import Path
from ponyguard_viqa.core import load_config, read_jsonl, stable_hash, write_jsonl
from ponyguard_viqa.llm import LocalLLM
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard, PromptSafeRAG
from ponyguard_viqa.retrieval import Embedder, Retriever

PIPELINES = {"basic_rag": BasicRAG, "prompt_safe_rag": PromptSafeRAG, "ponyguard": PonyGuard}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("system", choices=PIPELINES); parser.add_argument("--input", default="data/benchmark/dev.jsonl"); parser.add_argument("--output"); parser.add_argument("--limit", type=int); parser.add_argument("--mock", action="store_true"); args = parser.parse_args()
    config_name = {"basic_rag": "baseline", "prompt_safe_rag": "prompt_safe", "ponyguard": "ponyguard"}[args.system]
    config = load_config(f"configs/{config_name}.yaml")
    r, m = config["retrieval"], config["model"]
    retriever = Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"]))
    llm = LocalLLM(m["name"], "mock" if args.mock else m["backend"], m["max_tokens"])
    pipeline = PIPELINES[args.system](retriever, llm, r["top_k"])
    rows = read_jsonl(args.input)[:args.limit]
    output = args.output or f"runs/{args.system}/{Path(args.input).stem}_predictions.jsonl"
    predictions = [pipeline.run(row) for row in rows]
    write_jsonl(output, predictions)
    metadata = {"config": config, "sample_ids_sha256": stable_hash([row["sample_id"] for row in rows]), "prompt_versions": ["basic_rag_v2", "prompt_safe_rag_v2", "requirement_analyzer_v3", "evidence_checker_v2", "claim_verifier_v1"], "index": json.loads(Path("artifacts/index/metadata.json").read_text())}
    Path(output).with_suffix(".metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(output)

if __name__ == "__main__": main()
