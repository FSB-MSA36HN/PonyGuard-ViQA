# PonyGuard-ViQA

Vietnamese RAG benchmark comparing Basic RAG, Prompt-Safe RAG, and PonyGuard: a requirement-aware evidence harness with controlled inference and claim verification.

## Requirements

macOS on Apple Silicon, Python 3.10+, Git, and enough free disk space for the dataset/models. The default local model is `mlx-community/Qwen2.5-7B-Instruct-4bit`; no API key or server is needed.

## Commands

```bash
# 1. Setup: venv, dependencies, Ponytail clone, dataset and local models
make setup

# 2. Dataset preparation: normalize, EDA, corpus, frozen benchmark split
make prepare-data

# 3. Build the shared FAISS index
make build-index
make evaluate-retrieval

# 4. Run each system (use validation/dev while tuning; never modify test)
.venv/bin/python scripts/run_basic_rag.py --input data/benchmark/dev.jsonl
.venv/bin/python scripts/run_safe_rag.py --input data/benchmark/dev.jsonl
.venv/bin/python scripts/run_ponyguard.py --input data/benchmark/dev.jsonl

# 5. Run the final benchmark, then optional ablations/error analysis
make benchmark
.venv/bin/python scripts/run_ablation.py
.venv/bin/python scripts/error_analysis.py

# 6. Launch the demo
make demo
# Or run everything needed, then open the demo
./run.sh
```

Useful checks:

```bash
make verify-data
make test
# Fast offline integration smoke test after build-index
.venv/bin/python scripts/evaluate_all.py --input data/benchmark/dev.jsonl --limit 3 --mock
```

`data/benchmark/test.jsonl` is frozen on creation. Tune chunking, prompts, top-k and safeguards only with `dev.jsonl` and `validation.jsonl`; use `test.jsonl` only for the final protocol. Every run writes JSONL predictions under `runs/`; final metrics and the comparison table are in `reports/`.

## Architecture

All systems share the exact corpus, index, embedding model, top-k, generator model and split. PonyGuard performs requirement analysis → evidence/inference decision → restricted draft answer → atomic claim verification → final `ANSWER`, `ASK`, or `ABSTAIN` gate. The original Ponytail repository is cloned unchanged into `external/ponytail`; its pinned commit is recorded in `configs/dependencies.yaml`.

The comparison model is `mlx-community/Qwen2.5-7B-Instruct-4bit`. Basic RAG and Prompt-Safe RAG emit a literal cited evidence quote; an invalid quote/citation is withheld instead of being shown as a fact. Tune only on dev/validation; the frozen final test remains untouched.

The demo keeps one shared local model and retriever for both UI systems. Open **Timing theo stage** after a question to distinguish the one-time cold model/index load from normal inference; request timings are appended to `runs/ui_timing.jsonl`.
