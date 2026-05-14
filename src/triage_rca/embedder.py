import os

import anthropic
import httpx


def embed_text(text: str, client: anthropic.Anthropic | None = None) -> list[float]:
    """Embed text using voyage-3 via VoyageAI API.

    The Anthropic SDK (0.102.0) does not expose ``client.beta.embeddings``,
    so this falls back to calling the VoyageAI embeddings endpoint directly
    with httpx.  Requires VOYAGE_API_KEY to be set in the environment.

    ``client`` is accepted for future SDK compatibility but is not currently used.
    """
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY environment variable is not set")

    try:
        resp = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": text, "model": "voyage-3"},
            timeout=30,
        )
        resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        raise RuntimeError(f"Embedding request failed: {e}") from e

    data = resp.json().get("data", [])
    if not data:
        raise RuntimeError("VoyageAI returned empty data in embedding response")
    return data[0]["embedding"]
