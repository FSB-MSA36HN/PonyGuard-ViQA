#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -d .venv ] || [ ! -f data/raw/train.jsonl ]; then
  ./scripts/bootstrap.sh
fi
if [ ! -f data/processed/corpus.jsonl ]; then
  .venv/bin/python scripts/prepare_data.py
fi
if [ ! -f artifacts/index/faiss.index ]; then
  .venv/bin/python scripts/build_index.py
fi

exec .venv/bin/streamlit run src/ui/app.py --server.fileWatcherType none
