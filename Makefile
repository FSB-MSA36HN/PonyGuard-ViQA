.DEFAULT_GOAL := help

setup:
	chmod +x scripts/bootstrap.sh
	./scripts/bootstrap.sh
dataset:
	.venv/bin/python scripts/download_dataset.py
verify-data:
	.venv/bin/python scripts/verify_dataset.py
prepare-data:
	.venv/bin/python scripts/prepare_data.py
build-index:
	.venv/bin/python scripts/build_index.py
evaluate-retrieval:
	.venv/bin/python scripts/evaluate_retrieval.py
benchmark:
	.venv/bin/python scripts/evaluate_all.py
test:
	.venv/bin/python -m pytest -q
behavior-test:
	.venv/bin/python -m pytest -q tests/test_behavioral_matrix.py
live-behavioral:
	.venv/bin/python scripts/run_system.py ponyguard --input data/diagnostics/ponyguard_behavioral_live.jsonl --output runs/ponyguard/ponyguard_behavioral_live_predictions.jsonl
	.venv/bin/python scripts/report_live_diagnostics.py
demo:
	.venv/bin/streamlit run src/ui/app.py --server.fileWatcherType none
help:
	@echo "make setup | dataset | verify-data | prepare-data | build-index | evaluate-retrieval | benchmark | test | behavior-test | live-behavioral | demo"
