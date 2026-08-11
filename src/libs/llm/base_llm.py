"""Abstract base class for LLM providers.

This module defines the pluggable interface for Language Model providers,
enabling seamless switching between different backends (OpenAI, Azure, Ollama, etc.)
through configuration-driven instantiation. It also defines the text tool-call
protocol used by the Agentic RAG layer (Phase 6): ``chat_with_tools()``
serialises tool descriptions into a system-prompt appendix and parses the
model's ``<tool_call name="...">{"json"}</tool_call>`` replies back into
structured calls — no native function-calling required.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Message:
    """Represents a single message in a chat conversation.

    Attributes:
        role: The role of the message sender ('system', 'user', 'assistant',
            or 'tool' — the last for tool-call results in the agent loop).
        content: The text content of the message.
        tool_calls: Optional assistant metadata: ``[{"name", "arguments"}]``.
            Carried for trace/debug and future native function-calling; the
            default providers only serialise ``role``/``content``.
        tool_call_id: Optional id linking a ``role="tool"`` result back to the
            assistant tool call that produced it.
    """
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatResponse:
    """Response from an LLM chat completion.
    
    Attributes:
        content: The generated text response.
        model: The model identifier that generated the response.
        usage: Optional token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        raw_response: Optional raw response from the provider for debugging.
    """
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Any] = None


@dataclass
class ToolCall:
    """A parsed tool-call emitted by the LLM via the text protocol.

    Attributes:
        name: The tool name to invoke.
        arguments: Keyword arguments for the tool, as a JSON object.
    """
    name: str
    arguments: Dict[str, Any]


#: Single-line block a model emits to request a tool call.
_TOOL_CALL_RE = re.compile(r'<tool_call\s+name="([^"]+)">(.*?)</tool_call>', re.DOTALL)


def format_tool_call(name: str, arguments: Dict[str, Any]) -> str:
    """Serialize a tool call to the text protocol block."""
    return f'<tool_call name="{name}">{json.dumps(arguments, ensure_ascii=False)}</tool_call>'


def parse_tool_call(text: str) -> Tuple[Optional[ToolCall], Optional[str]]:
    """Parse a single ``<tool_call>`` block out of a model reply.

    Returns a ``(tool_call, error)`` pair so the agent loop needs no
    try/except on every iteration:

    - ``(ToolCall, None)`` — a well-formed block was found.
    - ``(None, error)`` — a block exists but its JSON payload is malformed
      or not an object; the caller feeds the message back to the model.
    - ``(None, None)`` — no block; the text is a final answer.
    """
    match = _TOOL_CALL_RE.search(text)
    if match is None:
        return None, None
    name = match.group(1)
    try:
        arguments = json.loads(match.group(2))
    except json.JSONDecodeError as exc:
        return None, f"tool_call 的 JSON 参数无法解析: {exc}"
    if not isinstance(arguments, dict):
        return None, (
            f"tool_call 参数必须是 JSON 对象，得到 {type(arguments).__name__}"
        )
    return ToolCall(name=name, arguments=arguments), None


def _summarize_schema(schema: Any) -> str:
    """Serialize a JSON-schema ``properties`` map to compact ``{"k": "type"}`` text."""
    if not isinstance(schema, dict):
        return "{}"
    props = schema.get("properties")
    if not isinstance(props, dict):
        return "{}"
    summary: Dict[str, str] = {}
    for key, spec in props.items():
        if isinstance(spec, dict) and spec.get("type"):
            summary[key] = str(spec["type"])
        else:
            summary[key] = "any"
    return json.dumps(summary, ensure_ascii=False)


def build_tools_system_prompt(tools: List[Dict[str, Any]]) -> str:
    """Build the tool-calling appendix injected into the system message.

    Args:
        tools: Tool descriptions as ``[{"name", "description", "input_schema"}]``.

    Returns:
        The appendix text telling the model how to request tool calls.
    """
    lines = [
        "## 可用工具",
        "你可以调用以下工具获取信息。调用时只输出下面这一行格式，不要输出其他任何内容：",
        '<tool_call name="工具名">{"参数名": 参数值}</tool_call>',
        "可用工具列表：",
    ]
    for tool in tools:
        name = tool.get("name", "?")
        description = tool.get("description", "")
        schema = _summarize_schema(tool.get("input_schema"))
        lines.append(f"- {name}: {description}  参数: {schema}")
    lines.append("若资料已足够，直接输出最终答案（不要在输出中混入 <tool_call>）。")
    return "\n".join(lines)


def _inject_system_appendix(messages: List[Message], appendix: str) -> List[Message]:
    """Return a copy of *messages* with *appendix* appended to the first system message.

    When no system message is present a synthetic one is prepended. The input
    list and its messages are never mutated — the agent loop reuses the same
    ``messages`` list across iterations, so an in-place append would grow the
    appendix every round.
    """
    if not messages:
        return [Message(role="system", content=appendix)]
    first_system = next((i for i, m in enumerate(messages) if m.role == "system"), None)
    if first_system is None:
        return [Message(role="system", content=appendix), *messages]
    copy = list(messages)
    original = copy[first_system]
    copy[first_system] = Message(
        role=original.role,
        content=f"{original.content}\n\n{appendix}",
        tool_calls=original.tool_calls,
        tool_call_id=original.tool_call_id,
    )
    return copy


class BaseLLM(ABC):
    """Abstract base class for LLM providers.
    
    All LLM implementations must inherit from this class and implement
    the chat() method. This ensures consistent interface across different
    providers (OpenAI, Azure, DeepSeek, Ollama, etc.).
    
    Design Principles Applied:
    - Pluggable: Subclasses can be swapped without changing upstream code.
    - Observable: Accepts optional TraceContext for observability integration.
    - Config-Driven: Instances are created via factory based on settings.
    """
    
    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Generate a chat completion response.
        
        Args:
            messages: List of conversation messages (role + content).
            trace: Optional TraceContext for observability (reserved for Stage F).
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.).
        
        Returns:
            ChatResponse containing the generated text and metadata.
        
        Raises:
            ValueError: If messages list is empty or malformed.
            RuntimeError: If the LLM provider call fails.
        """
        pass
    
    def validate_messages(self, messages: List[Message]) -> None:
        """Validate message list structure.
        
        Args:
            messages: List of messages to validate.
        
        Raises:
            ValueError: If messages list is empty or contains invalid roles.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        
        valid_roles = {"system", "user", "assistant", "tool"}
        for i, msg in enumerate(messages):
            if not isinstance(msg, Message):
                raise ValueError(f"Message at index {i} is not a Message instance")
            if msg.role not in valid_roles:
                raise ValueError(
                    f"Message at index {i} has invalid role '{msg.role}'. "
                    f"Must be one of: {valid_roles}"
                )
            if not msg.content or not msg.content.strip():
                raise ValueError(f"Message at index {i} has empty content")

    def chat_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat with tool descriptions injected into the system prompt (text protocol).

        Tool schemas are serialised into an appendix appended to a *copy* of the
        first system message; the caller's ``messages`` list is never mutated
        (the agent loop reuses the same list across iterations). The model then
        replies either with a final answer or a single ``<tool_call>`` line,
        parsed by :func:`parse_tool_call`. No native function-calling is used,
        so every provider works with zero changes.

        Args:
            messages: Conversation history to validate and extend.
            tools: Tool descriptions as ``[{"name", "description", "input_schema"}]``.
            trace: Optional TraceContext for observability.
            **kwargs: Provider-specific parameters forwarded to ``chat()``.

        Returns:
            The provider's :class:`ChatResponse`.
        """
        self.validate_messages(messages)
        appendix = build_tools_system_prompt(tools)
        injected = _inject_system_appendix(messages, appendix)
        return self.chat(injected, trace=trace, **kwargs)
