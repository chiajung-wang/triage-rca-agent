import os

import anthropic
import httpx


def embed_text(text: str, client: anthropic.Anthropic) -> list[float]:
    """Embed text using voyage-3 via VoyageAI API.

    The Anthropic SDK (0.102.0) does not expose ``client.beta.embeddings``,
    so this falls back to calling the VoyageAI embeddings endpoint directly
    with httpx.  Requires VOYAGE_API_KEY to be set in the environment.
    """
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
        json={"input": text, "model": "voyage-3"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
