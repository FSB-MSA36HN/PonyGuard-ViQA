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
demo:
	.venv/bin/streamlit run src/ui/app.py
help:
	@echo "make setup | dataset | verify-data | prepare-data | build-index | evaluate-retrieval | benchmark | test | demo"
