from airex_core.rag.chunker import chunk_text


class TestChunker:
    def test_returns_empty_for_blank_text(self):
        assert chunk_text("   ") == []

    def test_chunks_with_overlap(self):
        text = "0123456789" * 20
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert chunks  # at least one
        for chunk in chunks[:-1]:
            assert len(chunk) <= 50

        # Ensure overlap
        if len(chunks) >= 2:
            assert chunks[0][-10:] == chunks[1][:10]
