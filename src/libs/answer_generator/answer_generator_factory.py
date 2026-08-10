"""Factory for creating Answer Generator provider instances.

This module implements the Factory Pattern to instantiate the appropriate
AnswerGenerator provider based on configuration. It mirrors the
``EvaluatorFactory`` template (``_PROVIDERS`` + ``_LAZY_PROVIDERS`` + None
degradation) so switching providers only requires changing the
``answer_generator.provider`` field in ``settings.yaml``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.libs.answer_generator.base_answer_generator import (
    BaseAnswerGenerator,
    NoneAnswerGenerator,
)
from src.libs.answer_generator.extractive_answer_generator import (
    ExtractiveAnswerGenerator,
)
from src.libs.answer_generator.llm_answer_generator import LLMAnswerGenerator
from src.libs.answer_generator.template_answer_generator import (
    TemplateAnswerGenerator,
)

if TYPE_CHECKING:
    from src.core.settings import Settings


class AnswerGeneratorFactory:
    """Factory for creating AnswerGenerator provider instances.

    Design Principles Applied:
    - Factory Pattern: Centralizes object creation logic.
    - Config-Driven: Provider selection based on settings.yaml.
    - Fallback: Disabled generation returns NoneAnswerGenerator.
    - Fail-Fast: Raises clear errors for unknown providers.
    """

    _PROVIDERS: dict[str, type[BaseAnswerGenerator]] = {
        "extractive": ExtractiveAnswerGenerator,
        "llm": LLMAnswerGenerator,
        "template": TemplateAnswerGenerator,
    }

    # Lazy-loaded providers (import on demand to avoid hard dependencies).
    # Reserved to mirror EvaluatorFactory; none currently need lazy loading.
    _LAZY_PROVIDERS: dict[str, Any] = {}

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: type[BaseAnswerGenerator],
    ) -> None:
        """Register a new AnswerGenerator provider implementation.

        Args:
            name: The provider identifier (e.g., 'extractive', 'llm').
            provider_class: The BaseAnswerGenerator subclass implementing it.

        Raises:
            ValueError: If provider_class doesn't inherit from BaseAnswerGenerator.
        """
        if not issubclass(provider_class, BaseAnswerGenerator):
            raise ValueError(
                f"Provider class {provider_class.__name__} must inherit from "
                "BaseAnswerGenerator"
            )
        cls._PROVIDERS[name.lower()] = provider_class

    @classmethod
    def create(
        cls,
        settings: Settings,
        **override_kwargs: Any,
    ) -> BaseAnswerGenerator:
        """Create an AnswerGenerator instance based on configuration.

        Args:
            settings: Full ``Settings`` (with ``.answer_generator``) or a bare
                ``AnswerGeneratorSettings`` object.
            **override_kwargs: Optional parameters to override config values.

        Returns:
            An instance of the configured AnswerGenerator provider.

        Raises:
            ValueError: If the configured provider is unsupported or missing.
            RuntimeError: If provider initialization fails.
        """
        try:
            # Accept either full Settings (with .answer_generator attr) or
            # a bare AnswerGeneratorSettings object directly.
            ag_settings: Any
            if hasattr(settings, "answer_generator"):
                ag_settings = settings.answer_generator
            elif hasattr(settings, "provider") and hasattr(settings, "enabled"):
                ag_settings = settings
            else:
                raise AttributeError("settings has no 'answer_generator' attribute")
            if ag_settings is None:
                raise AttributeError("settings.answer_generator is None")
            provider_name = ag_settings.provider.lower()
            enabled = bool(ag_settings.enabled)
        except AttributeError as e:
            raise ValueError(
                "Missing required configuration: settings.answer_generator.provider. "
                "Please ensure 'answer_generator.provider' is specified in settings.yaml"
            ) from e

        if not enabled or provider_name in {"none", "disabled"}:
            return NoneAnswerGenerator(settings=settings, **override_kwargs)

        provider_class = cls._PROVIDERS.get(provider_name)
        if provider_class is None and provider_name in cls._LAZY_PROVIDERS:
            try:
                provider_class = cls._LAZY_PROVIDERS[provider_name]()
                cls._PROVIDERS[provider_name] = provider_class  # cache for next call
            except ImportError as e:
                raise ValueError(
                    f"Provider '{provider_name}' requires additional dependencies: {e}"
                ) from e
        if provider_class is None:
            all_providers = sorted(
                set(cls._PROVIDERS.keys()) | set(cls._LAZY_PROVIDERS.keys())
            )
            available = ", ".join(all_providers) if all_providers else "none"
            raise ValueError(
                f"Unsupported AnswerGenerator provider: '{provider_name}'. "
                f"Available providers: {available}."
            )

        try:
            return provider_class(settings=settings, **override_kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Failed to instantiate AnswerGenerator provider "
                f"'{provider_name}': {e}"
            ) from e

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names.

        Returns:
            Sorted list of available provider identifiers.
        """
        return sorted(cls._PROVIDERS.keys())
