from ponyguard_viqa.core import load_config, read_jsonl
from ponyguard_viqa.retrieval import Embedder, build_index

def main():
    config = load_config("configs/base.yaml"); r = config["retrieval"]
    metadata = build_index(read_jsonl("data/processed/corpus.jsonl"), "artifacts/index", Embedder(r["embedding_model"]), r["chunk_size"], r["chunk_overlap"])
    print(metadata)

if __name__ == "__main__": main()
