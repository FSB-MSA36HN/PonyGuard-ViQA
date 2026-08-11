from ponyguard_viqa.core import load_config

def main():
    c = load_config("configs/base.yaml")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(c["retrieval"]["embedding_model"])
    try:
        from mlx_lm import load
        load(c["model"]["name"])
    except ImportError:
        raise RuntimeError("MLX is required on this Apple Silicon project. Re-run bootstrap with Python 3.10+.")
    print("Models cached.")

if __name__ == "__main__": main()
