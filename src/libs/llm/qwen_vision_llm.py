"""Qwen (DashScope) Vision LLM implementation (OpenAI-compatible).

This module provides a Qwen-compatible Vision LLM implementation for
multimodal interactions (text + image). Supports qwen-vl-max and
similar vision-capable models via OpenAI-compatible endpoints.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from src.libs.llm.openai_vision_llm import OpenAIVisionLLM


class QwenVisionLLMError(RuntimeError):
    """Raised when Qwen Vision API call fails."""


class QwenVisionLLM(OpenAIVisionLLM):
    """Qwen Vision LLM provider implementation (OpenAI-compatible).

    This class implements the BaseVisionLLM interface using Qwen's
    OpenAI-compatible protocol. It supports both standard DashScope
    endpoints and custom MaaS deployments.

    Attributes:
        api_key: The API key for authentication.
        base_url: The base URL for the API.
        model: The model identifier / deployment name.
        max_image_size: Maximum image dimension in pixels (default 2048).
        default_temperature: Default temperature for generation.
        default_max_tokens: Default max tokens for generation.

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> vision_llm = QwenVisionLLM(settings)
        >>> image = ImageInput(path="diagram.png")
        >>> response = vision_llm.chat_with_image("Describe this", image)
    """

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_image_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen Vision LLM provider.

        Args:
            settings: Application settings containing vision_llm configuration.
            api_key: Optional API key override.
            base_url: Optional base URL override.
            max_image_size: Maximum image dimension in pixels for auto-compression.
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If required configuration is missing.
        """
        vision_settings = getattr(settings, 'vision_llm', None)

        # Resolve base URL: explicit > vision_llm.base_url > llm.base_url > DEFAULT
        resolved_base = (
            base_url
            or (getattr(vision_settings, 'base_url', None) if vision_settings else None)
            or getattr(settings.llm, 'base_url', None)
            or self.DEFAULT_BASE_URL
        )

        # Resolve API key: explicit > vision_llm.api_key > llm.api_key > env var
        resolved_key = (
            api_key
            or (getattr(vision_settings, 'api_key', None) if vision_settings else None)
            or getattr(settings.llm, 'api_key', None)
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Qwen API key not provided. Set in settings.yaml (vision_llm.api_key), "
                "DASHSCOPE_API_KEY environment variable, or pass api_key parameter."
            )

        super().__init__(
            settings,
            api_key=resolved_key,
            base_url=resolved_base,
            max_image_size=max_image_size,
            **kwargs,
        )
