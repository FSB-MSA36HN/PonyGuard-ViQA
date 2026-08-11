from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from ponyguard_viqa.core import load_config, read_jsonl, stable_hash, write_jsonl
from ponyguard_viqa.data import verify_frozen_split
from ponyguard_viqa.evaluation import audit_claims, markdown_table, metrics
from ponyguard_viqa.llm import LocalLLM

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="data/benchmark/test.jsonl"); parser.add_argument("--limit", type=int); parser.add_argument("--mock", action="store_true"); args = parser.parse_args()
    if Path(args.input).resolve() == Path("data/benchmark/test.jsonl").resolve(): verify_frozen_split(args.input)
    results = {}
    for system in ("basic_rag", "prompt_safe_rag", "ponyguard"):
        command = [sys.executable, "scripts/run_system.py", system, "--input", args.input]
        if args.limit: command += ["--limit", str(args.limit)]
        if args.mock: command += ["--mock"]
        subprocess.run(command, check=True)
        path = Path(f"runs/{system}/{Path(args.input).stem}_predictions.jsonl")
        rows = read_jsonl(path)
        config = load_config("configs/base.yaml")["model"]
        auditor = LocalLLM(config["name"], "mock" if args.mock else config["backend"], config["max_tokens"])
        for row in rows: row["audit_claims"] = audit_claims(row, auditor)
        write_jsonl(path, rows); results[system] = metrics(rows)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/benchmark_metrics.json").write_text(json.dumps(results, indent=2))
    Path("reports/benchmark_metadata.json").write_text(json.dumps({"input": args.input, "sample_ids_sha256": stable_hash([row["sample_id"] for row in read_jsonl(args.input)[:args.limit]]), "config": load_config("configs/base.yaml")}, ensure_ascii=False, indent=2))
    title = "# Benchmark results" + (" (mock smoke test — not final)" if args.mock else "")
    Path("reports/final_results.md").write_text(title + "\n\n" + markdown_table(results) + "\n")
    print(Path("reports/final_results.md").read_text())

if __name__ == "__main__": main()
