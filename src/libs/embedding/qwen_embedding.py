"""Qwen (DashScope) Embedding implementation (OpenAI-compatible).

This module provides the Qwen Embedding implementation that works with
Qwen's DashScope API via its OpenAI-compatible endpoint. It also
supports custom MaaS (Model as a Service) deployments.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from src.libs.embedding.openai_embedding import OpenAIEmbedding


class QwenEmbeddingError(RuntimeError):
    """Raised when Qwen Embedding API call fails."""


class QwenEmbedding(OpenAIEmbedding):
    """Qwen Embedding provider implementation (OpenAI-compatible).

    This class implements the BaseEmbedding interface for Qwen's DashScope
    Embeddings API. Qwen provides an OpenAI-compatible API, so all embed
    logic is inherited from OpenAIEmbedding. Only the default base URL,
    API key resolution, and model dimension lookup are customized.

    Supports both the standard DashScope endpoint and custom MaaS
    deployments by configuring ``base_url`` in settings.yaml.

    Attributes:
        api_key: The API key for authentication.
        model: The model identifier to use.
        dimensions: Optional dimension override.
        base_url: The base URL for the API.

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> embedding = QwenEmbedding(settings)
        >>> vectors = embedding.embed(["hello world", "test"])
    """

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Known Qwen embedding models and their default dimensions
    _MODEL_DIMENSIONS = {
        "text-embedding-v3": 1024,
        "text-embedding-v2": 1536,
        "text-embedding-v1": 1536,
    }

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen Embedding provider.

        Args:
            settings: Application settings containing Embedding configuration.
            api_key: Optional API key override (falls back to settings.embedding.api_key
                     or DASHSCOPE_API_KEY env var).
            base_url: Optional base URL override (falls back to settings.embedding.base_url
                      or DEFAULT_BASE_URL).
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If API key is not provided and not found in environment.
        """
        # Resolve base URL: explicit arg > settings.embedding.base_url > DEFAULT
        resolved_base = (
            base_url
            or getattr(settings.embedding, 'base_url', None)
            or self.DEFAULT_BASE_URL
        )

        # Resolve API key: explicit arg > settings.embedding.api_key > env var
        resolved_key = (
            api_key
            or getattr(settings.embedding, 'api_key', None)
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Qwen API key not provided. Set in settings.yaml (embedding.api_key), "
                "DASHSCOPE_API_KEY environment variable, or pass api_key parameter."
            )

        super().__init__(settings, api_key=resolved_key, base_url=resolved_base, **kwargs)

    def get_dimension(self) -> Optional[int]:
        """Get the embedding dimension for the configured Qwen model.

        Returns:
            The embedding dimension, or None if the model is not recognized.
        """
        if self.dimensions is not None:
            return self.dimensions
        return self._MODEL_DIMENSIONS.get(self.model)
