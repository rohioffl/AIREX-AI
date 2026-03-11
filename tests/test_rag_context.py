import uuid

from airex_core.rag.vector_store import IncidentMatch, RunbookMatch
from airex_core.services import rag_context


class TestFormatContextSections:
    def test_returns_none_when_no_matches(self):
        result = rag_context.format_context_sections([], [])
        assert result is None

    def test_formats_both_sections(self):
        runbook = RunbookMatch(
            source_type="runbook",
            source_id=uuid.uuid4(),
            chunk_index=0,
            content="Scale the service",
            metadata={"title": "Scaling Guide"},
            score=0.12,
        )
        incident = IncidentMatch(
            incident_id=uuid.uuid4(),
            summary="CPU saturated",
            score=0.33,
        )

        result = rag_context.format_context_sections([runbook], [incident])
        assert result is not None
        assert "Scaling Guide" in result
        assert "Similar Incidents" in result

    def test_truncates_long_context(self, monkeypatch):
        monkeypatch.setattr(rag_context.settings, "RAG_CONTEXT_MAX_CHARS", 50)
        runbook = RunbookMatch(
            source_type="runbook",
            source_id=uuid.uuid4(),
            chunk_index=0,
            content="a" * 200,
            metadata={"title": "Big"},
            score=0.5,
        )
        result = rag_context.format_context_sections([runbook], [])
        assert result is not None
        assert result.endswith(" …")
