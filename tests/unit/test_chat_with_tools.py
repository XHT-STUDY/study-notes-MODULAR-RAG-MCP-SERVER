"""Tests for the text tool-call protocol (Phase 6).

Covers the ``Message`` field extension, ``validate_messages`` accepting the
``"tool"`` role, and the ``chat_with_tools`` appendix injection contract —
most importantly that the caller's message list is never mutated.
"""

from __future__ import annotations

import pytest

from src.libs.llm.base_llm import (
    BaseLLM,
    ChatResponse,
    Message,
    build_tools_system_prompt,
    format_tool_call,
    parse_tool_call,
)


class RecordingLLM(BaseLLM):
    """Minimal stub capturing the messages handed to ``chat()``."""

    def __init__(self) -> None:
        self.last_messages: list[Message] = []

    def chat(self, messages, trace=None, **kwargs):  # type: ignore[no-untyped-def]
        self.last_messages = list(messages)
        return ChatResponse(content="ok", model="fake")


TOOLS = [
    {
        "name": "query_knowledge_hub",
        "description": "检索知识库",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_collections",
        "description": "列出所有集合",
        "input_schema": {"type": "object", "properties": {}},
    },
]


class TestMessageExtension:
    """New fields default to None and positional construction is unchanged."""

    def test_new_fields_default_none(self) -> None:
        msg = Message(role="user", content="hi")
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_positional_construction_unchanged(self) -> None:
        msg = Message("user", "hi")
        assert msg.role == "user"
        assert msg.content == "hi"
        assert msg.tool_calls is None

    def test_tool_fields_roundtrip(self) -> None:
        msg = Message(
            role="assistant",
            content='<tool_call name="query_knowledge_hub">{"query": "x"}</tool_call>',
            tool_calls=[{"name": "query_knowledge_hub", "arguments": {"query": "x"}}],
            tool_call_id="t1",
        )
        assert msg.tool_calls[0]["name"] == "query_knowledge_hub"
        assert msg.tool_call_id == "t1"


class TestValidateMessages:
    """The ``"tool"`` role is accepted; existing rejections stay."""

    def test_tool_role_accepted(self) -> None:
        llm = RecordingLLM()
        messages = [
            Message(role="assistant", content='<tool_call name="x">{}</tool_call>'),
            Message(role="tool", content='{"query": "x"}'),
        ]
        llm.validate_messages(messages)  # should not raise

    def test_system_user_assistant_still_accepted(self) -> None:
        llm = RecordingLLM()
        llm.validate_messages(
            [
                Message(role="system", content="sys"),
                Message(role="user", content="u"),
                Message(role="assistant", content="a"),
            ]
        )

    def test_invalid_role_still_rejected(self) -> None:
        llm = RecordingLLM()
        with pytest.raises(ValueError, match="invalid role 'invalid_role'"):
            llm.validate_messages([Message(role="invalid_role", content="x")])

    def test_empty_content_still_rejected(self) -> None:
        llm = RecordingLLM()
        with pytest.raises(ValueError, match="empty content"):
            llm.validate_messages([Message(role="tool", content="  ")])


class TestParseFormat:
    """format_tool_call / parse_tool_call round-trip contract."""

    def test_format_produces_single_line_block(self) -> None:
        assert (
            format_tool_call("query_knowledge_hub", {"query": "你好", "top_k": 3})
            == '<tool_call name="query_knowledge_hub">{"query": "你好", "top_k": 3}</tool_call>'
        )

    def test_parse_roundtrip(self) -> None:
        text = format_tool_call("query_knowledge_hub", {"query": "你好", "top_k": 3})
        call, err = parse_tool_call(text)
        assert err is None
        assert call is not None
        assert call.name == "query_knowledge_hub"
        assert call.arguments == {"query": "你好", "top_k": 3}

    def test_parse_no_block_is_final_answer(self) -> None:
        call, err = parse_tool_call("这是最终答案，没有调用工具。")
        assert call is None
        assert err is None

    def test_parse_malformed_json_returns_error(self) -> None:
        call, err = parse_tool_call('<tool_call name="x">{"query": }</tool_call>')
        assert call is None
        assert err is not None
        assert "无法解析" in err

    def test_parse_non_object_returns_error(self) -> None:
        call, err = parse_tool_call('<tool_call name="x">[1, 2, 3]</tool_call>')
        assert call is None
        assert err is not None
        assert "JSON 对象" in err

    def test_parse_finds_block_embedded_in_text(self) -> None:
        text = "我先查一下。\n" + format_tool_call("list_collections", {}) + "\n"
        call, err = parse_tool_call(text)
        assert err is None
        assert call is not None
        assert call.name == "list_collections"


class TestBuildToolsSystemPrompt:
    """The appendix lists tools with summarised schemas."""

    def test_contains_tool_names_and_format_line(self) -> None:
        prompt = build_tools_system_prompt(TOOLS)
        assert "query_knowledge_hub" in prompt
        assert "list_collections" in prompt
        assert '<tool_call name="工具名">{"参数名": 参数值}</tool_call>' in prompt

    def test_summarises_types(self) -> None:
        prompt = build_tools_system_prompt(TOOLS)
        assert '{"query": "string", "top_k": "integer"}' in prompt

    def test_empty_tools_produces_minimal_prompt(self) -> None:
        prompt = build_tools_system_prompt([])
        assert "可用工具" in prompt
        assert "- " not in prompt


class TestChatWithTools:
    """chat_with_tools validates, injects the appendix into a copy, delegates."""

    def test_injects_appendix_into_first_system_message(self) -> None:
        llm = RecordingLLM()
        messages = [
            Message(role="system", content="你是助手。"),
            Message(role="user", content="你好"),
        ]
        llm.chat_with_tools(messages, TOOLS)

        assert len(llm.last_messages) == 2
        sys_msg = llm.last_messages[0]
        assert sys_msg.role == "system"
        assert "## 可用工具" in sys_msg.content
        assert "你是助手。" in sys_msg.content

    def test_does_not_mutate_caller_messages(self) -> None:
        """Trap ②: the loop reuses the same list across iterations."""
        llm = RecordingLLM()
        messages = [
            Message(role="system", content="你是助手。"),
            Message(role="user", content="你好"),
        ]
        llm.chat_with_tools(messages, TOOLS)
        llm.chat_with_tools(messages, TOOLS)

        # Caller's list unchanged: single system message, no appendix leaked in.
        assert len(messages) == 2
        assert "## 可用工具" not in messages[0].content
        assert messages[0].content == "你是助手。"

        # And the injected copy does not grow across calls.
        assert len(llm.last_messages) == 2
        assert llm.last_messages[0].content.count("## 可用工具") == 1

    def test_synthetic_system_when_absent(self) -> None:
        llm = RecordingLLM()
        messages = [Message(role="user", content="你好")]
        llm.chat_with_tools(messages, TOOLS)

        assert llm.last_messages[0].role == "system"
        assert "## 可用工具" in llm.last_messages[0].content
        assert len(llm.last_messages) == 2

    def test_validates_before_delegating(self) -> None:
        llm = RecordingLLM()
        with pytest.raises(ValueError, match="Messages list cannot be empty"):
            llm.chat_with_tools([], TOOLS)

    def test_delegates_to_chat_without_mutating(self) -> None:
        llm = RecordingLLM()
        response = llm.chat_with_tools(
            [Message(role="user", content="hi")], TOOLS, temperature=0.0
        )
        assert isinstance(response, ChatResponse)
        assert response.content == "ok"
