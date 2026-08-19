from __future__ import annotations
import argparse, json
from pathlib import Path
from ponyguard_viqa.core import load_config, read_jsonl, stable_hash, write_jsonl
from ponyguard_viqa.llm import build_llm
from ponyguard_viqa.pipelines import BasicRAG, PonyGuard, PromptSafeRAG
from ponyguard_viqa.retrieval import Embedder, Retriever

PIPELINES = {"basic_rag": BasicRAG, "prompt_safe_rag": PromptSafeRAG, "ponyguard": PonyGuard}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("system", choices=PIPELINES); parser.add_argument("--input", default="data/benchmark/dev.jsonl"); parser.add_argument("--output"); parser.add_argument("--limit", type=int); parser.add_argument("--mock", action="store_true")
    # Diagnostic runs are only comparable across a fixed provider; automatic
    # Gemini/local fallback silently mixes two models within one run.
    parser.add_argument("--model", help="pin one provider, e.g. 'local', instead of the configured auto-fallback")
    args = parser.parse_args()
    config_name = {"basic_rag": "baseline", "prompt_safe_rag": "prompt_safe", "ponyguard": "ponyguard"}[args.system]
    config = load_config(f"configs/{config_name}.yaml")
    r, m = config["retrieval"], config["model"]
    retriever = Retriever("artifacts/index/faiss.index", "artifacts/index/documents.jsonl", Embedder(r["embedding_model"]))
    llm = build_llm(m, mock=args.mock, selected_model=args.model)
    options = {"stage_tokens": m.get("stage_max_tokens")}
    if args.system == "ponyguard": options["intent_first"] = config.get("ponyguard", {}).get("intent_first", False)
    pipeline = PIPELINES[args.system](retriever, llm, r["top_k"], **options)
    rows = read_jsonl(args.input)[:args.limit]
    output = args.output or f"runs/{args.system}/{Path(args.input).stem}_predictions.jsonl"
    predictions = [pipeline.run(row) for row in rows]
    write_jsonl(output, predictions)
    metadata = {"config": config, "sample_ids_sha256": stable_hash([row["sample_id"] for row in rows]), "prompt_versions": ["basic_rag_v3", "prompt_safe_rag_v3", "semantic_evidence_v5", "fact_extractor_v1", "requirement_recovery_v1", "evidence_recovery_v1", "clarification_adjudicator_v3", "clarity_auditor_v1", "clarification_writer_v2", "claim_verifier_v2"], "pinned_model": args.model or "", "policy_version": config.get("ponyguard", {}).get("policy_version", "grounded_baseline_v1"), "grounding_validator": "literal_quote_entity_relation_binding_v3", "index": json.loads(Path("artifacts/index/metadata.json").read_text())}
    Path(output).with_suffix(".metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(output)

if __name__ == "__main__": main()
