"""Tests for the Phase 6 AgentFactory (strategy selection + None degradation)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.agent import AgentFactory
from src.core.agent.agent_runner import (
    PlanAndExecuteAgent,
    ReActAgent,
    SelfAskAgent,
)
from src.core.agent.base_agent import NoneAgent
from src.core.settings import AgentSettings


def _settings(agent: AgentSettings | None) -> SimpleNamespace:
    return SimpleNamespace(agent=agent)


class TestDisabledDegradation:
    def test_disabled_returns_none_agent(self) -> None:
        agent = AgentFactory.create(_settings(AgentSettings(enabled=False)))
        assert isinstance(agent, NoneAgent)
        assert agent.is_enabled is False

    def test_no_agent_block_returns_none_agent(self) -> None:
        agent = AgentFactory.create(_settings(None))
        assert isinstance(agent, NoneAgent)

    def test_settings_none_returns_none_agent(self) -> None:
        agent = AgentFactory.create(None)
        assert isinstance(agent, NoneAgent)

    def test_disabled_keeps_strategy(self) -> None:
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=False, strategy="self_ask"))
        )
        assert agent.strategy == "self_ask"

    def test_disabled_forwards_direct_retriever(self) -> None:
        dr = lambda q: None  # noqa: E731
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=False)), direct_retriever=dr
        )
        assert isinstance(agent, NoneAgent)
        assert agent._direct_retriever is dr


class TestStrategySelection:
    def test_create_react(self) -> None:
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=True, strategy="react"))
        )
        assert isinstance(agent, ReActAgent)
        assert agent.strategy == "react"

    def test_create_plan_and_execute(self) -> None:
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=True, strategy="plan_and_execute"))
        )
        assert isinstance(agent, PlanAndExecuteAgent)

    def test_create_self_ask(self) -> None:
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=True, strategy="self_ask"))
        )
        assert isinstance(agent, SelfAskAgent)

    def test_accepts_bare_agent_settings(self) -> None:
        agent = AgentFactory.create(AgentSettings(enabled=True, strategy="react"))
        assert isinstance(agent, ReActAgent)

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported agent strategy"):
            AgentFactory.create(
                _settings(AgentSettings(enabled=True, strategy="nope"))
            )

    def test_override_kwargs_forwarded(self) -> None:
        llm = object()
        agent = AgentFactory.create(
            _settings(AgentSettings(enabled=True, strategy="react")),
            llm=llm,
            max_iterations=3,
        )
        assert isinstance(agent, ReActAgent)
        assert agent._llm is llm
        assert agent._max_iterations == 3


class TestRegistration:
    def test_register_and_list(self) -> None:
        AgentFactory.register_provider("dummy_agent", ReActAgent)
        assert "dummy_agent" in AgentFactory.list_providers()

    def test_register_rejects_non_agent(self) -> None:
        with pytest.raises(ValueError, match="must inherit from BaseAgent"):
            AgentFactory.register_provider("bad", dict)

    def test_list_providers_contains_strategies(self) -> None:
        providers = AgentFactory.list_providers()
        for name in ("react", "plan_and_execute", "self_ask"):
            assert name in providers
