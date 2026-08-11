from datasets import load_dataset
from ponyguard_viqa.core import write_jsonl

DATASET = "taidng/UIT-ViQuAD2.0"

def main():
    dataset = load_dataset(DATASET)
    for name, split in dataset.items():
        write_jsonl(f"data/raw/{name}.jsonl", [dict(row) for row in split])
        print(f"Saved {name}: {len(split)} rows")

if __name__ == "__main__": main()
