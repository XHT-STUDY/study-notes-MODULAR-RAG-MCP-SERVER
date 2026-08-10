"""Unit tests for MCPToolResponse answer-field serialization."""

import json

import pytest

from src.core.response.response_builder import MCPToolResponse


def _extract_json_payload(block_text: str) -> dict:
    """Pull the JSON object out of the ``References (JSON)`` markdown block."""
    json_part = block_text.split("```json\n", 1)[1]
    return json.loads(json_part.rsplit("\n```", 1)[0])


@pytest.mark.unit
class TestMCPToolResponseAnswer:
    """Tests for the backward-compatible answer fields on MCPToolResponse."""

    def test_defaults_are_none(self) -> None:
        response = MCPToolResponse(content="x")
        assert response.answer is None
        assert response.confidence is None
        assert response.refusal_reason is None

    def test_to_dict_omits_answer_keys_when_none(self) -> None:
        response = MCPToolResponse(content="x", metadata={"query": "q"})
        structured = response.to_dict()["structuredContent"]

        assert "answer" not in structured
        assert "confidence" not in structured
        assert "refusalReason" not in structured

    def test_to_dict_includes_answer_keys(self) -> None:
        response = MCPToolResponse(content="x", answer="答案", confidence=0.9)
        structured = response.to_dict()["structuredContent"]

        assert structured["answer"] == "答案"
        assert structured["confidence"] == 0.9
        assert "refusalReason" not in structured

    def test_to_dict_includes_refusal_reason(self) -> None:
        response = MCPToolResponse(
            content="x", answer="答案", confidence=0.2,
            refusal_reason="low_confidence",
        )
        structured = response.to_dict()["structuredContent"]

        assert structured["refusalReason"] == "low_confidence"

    def test_to_mcp_content_emits_json_block_for_answer_only(self) -> None:
        # No citations/metadata, but answer present → JSON block must be emitted.
        response = MCPToolResponse(content="x", answer="答案", confidence=0.8)
        blocks = response.to_mcp_content()

        assert len(blocks) == 2
        payload = _extract_json_payload(blocks[1].text)
        assert payload["answer"] == "答案"
        assert payload["confidence"] == 0.8

    def test_to_mcp_content_without_answer_keeps_single_block(self) -> None:
        response = MCPToolResponse(content="x")
        blocks = response.to_mcp_content()

        assert len(blocks) == 1
        assert blocks[0].type == "text"
