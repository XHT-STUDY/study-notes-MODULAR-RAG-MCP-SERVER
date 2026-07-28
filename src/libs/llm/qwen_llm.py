"""Qwen (DashScope) LLM implementation (OpenAI-compatible).

This module provides the Qwen LLM implementation that works with
Qwen's DashScope API via its OpenAI-compatible endpoint. It also
supports custom MaaS (Model as a Service) deployments.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from src.libs.llm.openai_llm import OpenAILLM


class QwenLLMError(RuntimeError):
    """Raised when Qwen API call fails."""


class QwenLLM(OpenAILLM):
    """Qwen LLM provider implementation (OpenAI-compatible).

    This class implements the BaseLLM interface for Qwen's DashScope API.
    Qwen provides an OpenAI-compatible API, so all chat and HTTP logic
    is inherited from OpenAILLM. Only the default base URL and API key
    resolution are customized.

    Supports both the standard DashScope endpoint and custom MaaS
    deployments by configuring ``base_url`` in settings.yaml.

    Attributes:
        api_key: The API key for authentication.
        base_url: The base URL for the API.
        model: The model identifier to use.
        default_temperature: Default temperature for generation.
        default_max_tokens: Default max tokens for generation.

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> llm = QwenLLM(settings)
        >>> response = llm.chat([Message(role='user', content='Hello')])
    """

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen LLM provider.

        Args:
            settings: Application settings containing LLM configuration.
            api_key: Optional API key override (falls back to settings.llm.api_key
                     or DASHSCOPE_API_KEY env var).
            base_url: Optional base URL override (falls back to settings.llm.base_url
                      or DEFAULT_BASE_URL).
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If API key is not provided and not found in environment.
        """
        # Resolve base URL: explicit arg > settings.llm.base_url > DEFAULT
        resolved_base = (
            base_url
            or getattr(settings.llm, 'base_url', None)
            or self.DEFAULT_BASE_URL
        )

        # Resolve API key: explicit arg > settings.llm.api_key > env var
        resolved_key = (
            api_key
            or getattr(settings.llm, 'api_key', None)
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Qwen API key not provided. Set in settings.yaml (llm.api_key), "
                "DASHSCOPE_API_KEY environment variable, or pass api_key parameter."
            )

        # Pass resolved credentials to OpenAILLM.__init__.
        # Since we always pass a non-None base_url, OpenAILLM takes the
        # `if base_url:` branch, sets _use_azure_auth=False, and uses
        # Bearer token auth -- which is correct for Qwen.
        super().__init__(settings, api_key=resolved_key, base_url=resolved_base, **kwargs)
