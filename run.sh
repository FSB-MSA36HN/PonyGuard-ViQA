#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PORT="${PORT:-8000}"

if [ ! -d .venv ] || [ ! -f data/raw/train.jsonl ]; then
  ./scripts/bootstrap.sh
fi
if [ ! -f data/processed/corpus.jsonl ]; then
  .venv/bin/python scripts/prepare_data.py
fi
if [ ! -f artifacts/index/faiss.index ]; then
  .venv/bin/python scripts/build_index.py
fi

command -v npm >/dev/null || { echo "Cần Node.js/npm để build UI: https://nodejs.org"; exit 1; }
[ -d web/node_modules ] || (cd web && npm install)
# Rebuild only when a source file is newer than the bundle.
if [ ! -f web/dist/index.html ] || [ -n "$(find web/src web/index.html web/package.json -newer web/dist/index.html -print -quit)" ]; then
  (cd web && npm run build)
fi

# One process serves the React bundle and the pipeline API on the same port.
exec .venv/bin/python src/api/server.py "$PORT"
