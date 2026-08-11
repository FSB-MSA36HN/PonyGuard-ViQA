#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p external data/raw data/processed data/benchmark artifacts/index runs reports
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
command -v "$PYTHON_BIN" >/dev/null || { echo "Python 3.12 is required for the tested MLX/Torch stack." >&2; exit 1; }
[ -d .venv ] || "$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e '.[test]'
if [ ! -d external/ponytail ]; then git clone https://github.com/DietrichGebert/ponytail.git external/ponytail; fi
PONY_COMMIT="$(git -C external/ponytail rev-parse HEAD)"
python - "$PONY_COMMIT" <<'PY'
import sys, yaml
p = 'configs/dependencies.yaml'; d = yaml.safe_load(open(p)); d['ponytail']['commit'] = sys.argv[1]
open(p, 'w').write(yaml.safe_dump(d, sort_keys=False))
PY
python scripts/download_dataset.py
python scripts/verify_dataset.py
python scripts/warm_models.py
echo 'Bootstrap complete. Run: make prepare-data && make build-index'
