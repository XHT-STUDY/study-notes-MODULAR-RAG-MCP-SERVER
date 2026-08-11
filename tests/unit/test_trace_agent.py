"""Tests for the ``"agent"`` trace type (Phase 6).

Agent traces are recorded by the ``agent_query`` tool. This file locks the
widened ``trace_type`` literal and verifies agent stage recording round-trips
through ``to_dict()``.
"""

from __future__ import annotations

import json

from src.core.trace.trace_context import TraceContext


class TestTraceAgent:
    """The ``"agent"`` trace type is accepted and serialised."""

    def test_agent_trace_type_accepted(self) -> None:
        tc = TraceContext(trace_type="agent")
        assert tc.trace_type == "agent"

    def test_to_dict_trace_type_is_agent(self) -> None:
        tc = TraceContext(trace_type="agent")
        tc.finish()
        assert tc.to_dict()["trace_type"] == "agent"

    def test_json_serialisable(self) -> None:
        tc = TraceContext(trace_type="agent")
        tc.record_stage("agent_router", {"target": "direct_rag"})
        tc.finish()
        parsed = json.loads(json.dumps(tc.to_dict()))
        assert parsed["trace_type"] == "agent"
        assert parsed["stages"][0]["stage"] == "agent_router"

    def test_agent_stages_recorded_in_order(self) -> None:
        tc = TraceContext(trace_type="agent")
        for name in (
            "agent_router",
            "agent_tool_call",
            "agent_reflection",
            "agent_final",
        ):
            tc.record_stage(name, {})
        assert [s["stage"] for s in tc.stages] == [
            "agent_router",
            "agent_tool_call",
            "agent_reflection",
            "agent_final",
        ]

    def test_get_stage_data_works_for_agent(self) -> None:
        tc = TraceContext(trace_type="agent")
        tc.record_stage("agent_final", {"strategy": "react"})
        assert tc.get_stage_data("agent_final") == {"strategy": "react"}

    def test_default_remains_query(self) -> None:
        """Backward compat: default trace_type is still ``"query"``."""
        assert TraceContext().trace_type == "query"
