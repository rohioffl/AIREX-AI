from types import SimpleNamespace

import pytest

from airex_core.llm.embeddings import EmbeddingsClient


@pytest.mark.asyncio
async def test_embed_texts_uses_proxy_embedding_alias(monkeypatch):
    monkeypatch.setattr(
        "airex_core.llm.embeddings.settings.LLM_BASE_URL",
        "http://localhost:4000",
    )
    monkeypatch.setattr(
        "airex_core.llm.embeddings.settings.LLM_EMBEDDING_MODEL",
        "text-embedding-3-large",
    )

    captured: dict[str, object] = {}

    async def fake_aembedding(**kwargs):
        captured.update(kwargs)
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr("airex_core.llm.embeddings.litellm.aembedding", fake_aembedding)

    client = EmbeddingsClient()
    vectors = await client.embed_texts(["cpu saturation on web-1"])

    assert vectors == [[0.1, 0.2, 0.3]]
    assert captured["model"] == "openai/text-embedding"
    assert captured["api_base"] == "http://localhost:4000"
    assert "dimensions" not in captured
