import json
from pathlib import Path
from ponyguard_viqa.core import write_jsonl
from ponyguard_viqa.data import clarification_set, corpus, eda, normalize_raw, write_splits

def main():
    rows = normalize_raw("data/raw", "data/processed/viquad_normalized.jsonl")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/data_eda.json").write_text(json.dumps(eda(rows), ensure_ascii=False, indent=2))
    write_jsonl("data/processed/corpus.jsonl", corpus(rows))
    write_jsonl("data/benchmark/clarification_test.jsonl", clarification_set(rows))
    print(json.dumps(write_splits(rows, "data/benchmark"), indent=2))

if __name__ == "__main__": main()
