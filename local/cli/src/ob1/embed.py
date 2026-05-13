import requests

from .config import Config


class EmbedError(RuntimeError):
    pass


def generate(text: str, cfg: Config) -> list[float]:
    truncated = text[:8000]
    try:
        resp = requests.post(
            f"{cfg.ollama_url}/api/embed",
            json={"model": cfg.embed_model, "input": truncated},
            timeout=120,
        )
    except requests.RequestException as e:
        raise EmbedError(f"cannot reach Ollama at {cfg.ollama_url}: {e}") from e

    if resp.status_code != 200:
        raise EmbedError(f"Ollama returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    try:
        embedding = data["embeddings"][0]
    except (KeyError, IndexError) as e:
        raise EmbedError(f"unexpected Ollama response: {data}") from e

    if len(embedding) != cfg.embed_dim:
        raise EmbedError(
            f"embedding dim {len(embedding)} != configured OB1_EMBED_DIM={cfg.embed_dim}. "
            f"Model {cfg.embed_model} likely emits {len(embedding)}-dim vectors; "
            "rebuild the DB volume with a matching schema or pick a matching model."
        )
    return embedding


def ping(cfg: Config) -> str:
    resp = requests.get(f"{cfg.ollama_url}/api/tags", timeout=5)
    resp.raise_for_status()
    return resp.text
