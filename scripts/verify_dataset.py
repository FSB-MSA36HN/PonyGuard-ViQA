from pathlib import Path
from ponyguard_viqa.core import read_jsonl

def main():
    paths = list(Path("data/raw").glob("*.jsonl"))
    if not paths: raise RuntimeError("No raw data found; run scripts/download_dataset.py")
    for path in paths:
        rows = read_jsonl(path)
        if not rows: raise RuntimeError(f"Empty dataset split: {path}")
        required = {"context", "question"}
        if not required <= rows[0].keys(): raise RuntimeError(f"{path} missing {required - rows[0].keys()}")
        print(f"{path}: {len(rows)} valid JSONL rows")

if __name__ == "__main__": main()
