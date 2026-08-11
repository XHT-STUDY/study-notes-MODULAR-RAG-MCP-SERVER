"""Configuration loading and validation for the Modular RAG MCP Server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Repo root & path resolution
# ---------------------------------------------------------------------------
# Anchored to this file's location: <repo>/src/core/settings.py → parents[2]
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# Default absolute path to settings.yaml
DEFAULT_SETTINGS_PATH: Path = REPO_ROOT / "config" / "settings.yaml"

# Default absolute path to the .env override file (loaded by load_settings if present)
DEFAULT_ENV_FILE: Path = REPO_ROOT / "config" / ".env"


def resolve_path(relative: Union[str, Path]) -> Path:
    """Resolve a repo-relative path to an absolute path.

    If *relative* is already absolute it is returned as-is.  Otherwise
    it is resolved against :data:`REPO_ROOT`.

    >>> resolve_path("config/settings.yaml")  # doctest: +SKIP
    PosixPath('/home/user/Modular-RAG-MCP-Server/config/settings.yaml')
    """
    p = Path(relative)
    if p.is_absolute():
        return p
    return (REPO_ROOT / p).resolve()


class SettingsError(ValueError):
    """Raised when settings validation fails."""


def _require_mapping(data: Dict[str, Any], key: str, path: str) -> Dict[str, Any]:
    value = data.get(key)
    if value is None:
        raise SettingsError(f"Missing required field: {path}.{key}")
    if not isinstance(value, dict):
        raise SettingsError(f"Expected mapping for field: {path}.{key}")
    return value


def _require_value(data: Dict[str, Any], key: str, path: str) -> Any:
    if key not in data or data.get(key) is None:
        raise SettingsError(f"Missing required field: {path}.{key}")
    return data[key]


def _require_str(data: Dict[str, Any], key: str, path: str) -> str:
    value = _require_value(data, key, path)
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"Expected non-empty string for field: {path}.{key}")
    return value


def _require_int(data: Dict[str, Any], key: str, path: str) -> int:
    value = _require_value(data, key, path)
    if not isinstance(value, int):
        raise SettingsError(f"Expected integer for field: {path}.{key}")
    return value


def _require_number(data: Dict[str, Any], key: str, path: str) -> float:
    value = _require_value(data, key, path)
    if not isinstance(value, (int, float)):
        raise SettingsError(f"Expected number for field: {path}.{key}")
    return float(value)


def _require_bool(data: Dict[str, Any], key: str, path: str) -> bool:
    value = _require_value(data, key, path)
    if not isinstance(value, bool):
        raise SettingsError(f"Expected boolean for field: {path}.{key}")
    return value


def _require_list(data: Dict[str, Any], key: str, path: str) -> List[Any]:
    value = _require_value(data, key, path)
    if not isinstance(value, list):
        raise SettingsError(f"Expected list for field: {path}.{key}")
    return value


def _optional(value: Any) -> Optional[str]:
    """Coerce a blank value to ``None`` for optional string fields.

    A blank YAML value (``""``) is treated as "not configured" so that
    consumers can rely on ``None`` meaning "unset" — matching the behaviour
    of a missing key. Non-string values are also treated as unset.
    """
    if isinstance(value, str):
        return value.strip() or None
    return None


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    temperature: float
    max_tokens: int
    # Azure/OpenAI-specific optional fields
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    azure_endpoint: Optional[str] = None
    deployment_name: Optional[str] = None
    # Ollama-specific optional fields
    base_url: Optional[str] = None


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    dimensions: int
    # Azure-specific optional fields
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    azure_endpoint: Optional[str] = None
    deployment_name: Optional[str] = None
    # Ollama-specific optional fields
    base_url: Optional[str] = None


@dataclass(frozen=True)
class VectorStoreSettings:
    provider: str
    persist_directory: str
    collection_name: str


@dataclass(frozen=True)
class RetrievalSettings:
    dense_top_k: int
    sparse_top_k: int
    fusion_top_k: int
    rrf_k: int


@dataclass(frozen=True)
class RerankSettings:
    enabled: bool
    provider: str
    model: str
    top_k: int


@dataclass(frozen=True)
class EvaluationSettings:
    enabled: bool
    provider: str
    metrics: List[str]
    # Composite backend: list of provider names (e.g. [custom, ragas]) that the
    # CompositeEvaluator composes.  Only used when provider == "composite".
    backends: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ObservabilitySettings:
    log_level: str
    trace_enabled: bool
    trace_file: str
    structured_logging: bool


@dataclass(frozen=True)
class VisionLLMSettings:
    enabled: bool
    provider: str
    model: str
    max_image_size: int
    api_key: Optional[str] = None
    api_version: Optional[str] = None
    azure_endpoint: Optional[str] = None
    deployment_name: Optional[str] = None
    base_url: Optional[str] = None


@dataclass(frozen=True)
class IngestionSettings:
    chunk_size: int
    chunk_overlap: int
    splitter: str
    batch_size: int
    chunk_refiner: Optional[Dict[str, Any]] = None  # 动态配置
    metadata_enricher: Optional[Dict[str, Any]] = None  # 动态配置


@dataclass(frozen=True)
class AnswerGeneratorSettings:
    """Configuration for the generative Q&A layer (Phase 2).

    ``provider`` values: ``extractive`` (offline, no key), ``llm`` (reuses the
    ``llm`` section via LLMFactory), ``template`` (baseline/tests), ``none``.
    ``enabled=false`` (or ``provider: none/disabled``) returns a
    ``NoneAnswerGenerator`` so the query chain stays retrieval-only.
    """

    enabled: bool
    provider: str
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 1024
    confidence_threshold: float = 0.5
    max_chunks: int = 3


@dataclass(frozen=True)
class PromptsSettings:
    """Role → prompt file name mapping (without the ``.md`` extension).

    ``None`` (or an absent key) falls back to the role name as the default
    file name, e.g. role ``chunk_refinement`` → ``prompts/chunk_refinement.md``.
    """

    chunk_refinement: Optional[str] = None
    metadata_enrichment: Optional[str] = None
    image_captioning: Optional[str] = None
    rerank: Optional[str] = None

    def resolve(self, role: str) -> str:
        """Resolve a role name to its configured prompt file stem."""
        value = getattr(self, role, None)
        return value or role


@dataclass(frozen=True)
class Settings:
    llm: LLMSettings
    embedding: EmbeddingSettings
    vector_store: VectorStoreSettings
    retrieval: RetrievalSettings
    rerank: RerankSettings
    evaluation: EvaluationSettings
    observability: ObservabilitySettings
    ingestion: Optional[IngestionSettings] = None
    vision_llm: Optional[VisionLLMSettings] = None
    answer_generator: Optional[AnswerGeneratorSettings] = None
    prompts: Optional[PromptsSettings] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        if not isinstance(data, dict):
            raise SettingsError("Settings root must be a mapping")

        llm = _require_mapping(data, "llm", "settings")
        embedding = _require_mapping(data, "embedding", "settings")
        vector_store = _require_mapping(data, "vector_store", "settings")
        retrieval = _require_mapping(data, "retrieval", "settings")
        rerank = _require_mapping(data, "rerank", "settings")
        evaluation = _require_mapping(data, "evaluation", "settings")
        observability = _require_mapping(data, "observability", "settings")

        ingestion_settings = None
        if "ingestion" in data:
            ingestion = _require_mapping(data, "ingestion", "settings")
            ingestion_settings = IngestionSettings(
                chunk_size=_require_int(ingestion, "chunk_size", "ingestion"),
                chunk_overlap=_require_int(ingestion, "chunk_overlap", "ingestion"),
                splitter=_require_str(ingestion, "splitter", "ingestion"),
                batch_size=_require_int(ingestion, "batch_size", "ingestion"),
                chunk_refiner=ingestion.get("chunk_refiner"),  # 可选配置
                metadata_enricher=ingestion.get("metadata_enricher"),  # 可选配置
            )

        vision_llm_settings = None
        if "vision_llm" in data:
            vision_llm = _require_mapping(data, "vision_llm", "settings")
            vision_llm_settings = VisionLLMSettings(
                enabled=_require_bool(vision_llm, "enabled", "vision_llm"),
                provider=_require_str(vision_llm, "provider", "vision_llm"),
                model=_require_str(vision_llm, "model", "vision_llm"),
                max_image_size=_require_int(vision_llm, "max_image_size", "vision_llm"),
                api_key=_optional(vision_llm.get("api_key")),
                api_version=_optional(vision_llm.get("api_version")),
                azure_endpoint=_optional(vision_llm.get("azure_endpoint")),
                deployment_name=_optional(vision_llm.get("deployment_name")),
                base_url=_optional(vision_llm.get("base_url")),
            )

        answer_generator_settings = None
        if "answer_generator" in data:
            ag = _require_mapping(data, "answer_generator", "settings")
            answer_generator_settings = AnswerGeneratorSettings(
                enabled=_require_bool(ag, "enabled", "answer_generator"),
                provider=_require_str(ag, "provider", "answer_generator"),
                model=str(ag.get("model", "") or ""),
                temperature=(
                    _require_number(ag, "temperature", "answer_generator")
                    if "temperature" in ag
                    else 0.0
                ),
                max_tokens=(
                    _require_int(ag, "max_tokens", "answer_generator")
                    if "max_tokens" in ag
                    else 1024
                ),
                confidence_threshold=(
                    _require_number(ag, "confidence_threshold", "answer_generator")
                    if "confidence_threshold" in ag
                    else 0.5
                ),
                max_chunks=(
                    _require_int(ag, "max_chunks", "answer_generator")
                    if "max_chunks" in ag
                    else 3
                ),
            )

        prompts_settings = None
        if "prompts" in data:
            prompts_map = _require_mapping(data, "prompts", "settings")
            prompts_settings = PromptsSettings(
                chunk_refinement=_optional(prompts_map.get("chunk_refinement")),
                metadata_enrichment=_optional(prompts_map.get("metadata_enrichment")),
                image_captioning=_optional(prompts_map.get("image_captioning")),
                rerank=_optional(prompts_map.get("rerank")),
            )

        settings = cls(
            llm=LLMSettings(
                provider=_require_str(llm, "provider", "llm"),
                model=_require_str(llm, "model", "llm"),
                temperature=_require_number(llm, "temperature", "llm"),
                max_tokens=_require_int(llm, "max_tokens", "llm"),
                api_key=_optional(llm.get("api_key")),
                api_version=_optional(llm.get("api_version")),
                azure_endpoint=_optional(llm.get("azure_endpoint")),
                deployment_name=_optional(llm.get("deployment_name")),
                base_url=_optional(llm.get("base_url")),
            ),
            embedding=EmbeddingSettings(
                provider=_require_str(embedding, "provider", "embedding"),
                model=_require_str(embedding, "model", "embedding"),
                dimensions=_require_int(embedding, "dimensions", "embedding"),
                api_key=_optional(embedding.get("api_key")),
                api_version=_optional(embedding.get("api_version")),
                azure_endpoint=_optional(embedding.get("azure_endpoint")),
                deployment_name=_optional(embedding.get("deployment_name")),
                base_url=_optional(embedding.get("base_url")),
            ),
            vector_store=VectorStoreSettings(
                provider=_require_str(vector_store, "provider", "vector_store"),
                persist_directory=_require_str(vector_store, "persist_directory", "vector_store"),
                collection_name=_require_str(vector_store, "collection_name", "vector_store"),
            ),
            retrieval=RetrievalSettings(
                dense_top_k=_require_int(retrieval, "dense_top_k", "retrieval"),
                sparse_top_k=_require_int(retrieval, "sparse_top_k", "retrieval"),
                fusion_top_k=_require_int(retrieval, "fusion_top_k", "retrieval"),
                rrf_k=_require_int(retrieval, "rrf_k", "retrieval"),
            ),
            rerank=RerankSettings(
                enabled=_require_bool(rerank, "enabled", "rerank"),
                provider=_require_str(rerank, "provider", "rerank"),
                model=_require_str(rerank, "model", "rerank"),
                top_k=_require_int(rerank, "top_k", "rerank"),
            ),
            evaluation=EvaluationSettings(
                enabled=_require_bool(evaluation, "enabled", "evaluation"),
                provider=_require_str(evaluation, "provider", "evaluation"),
                metrics=[str(item) for item in _require_list(evaluation, "metrics", "evaluation")],
                backends=(
                    [str(item) for item in _require_list(evaluation, "backends", "evaluation")]
                    if "backends" in evaluation
                    else []
                ),
            ),
            observability=ObservabilitySettings(
                log_level=_require_str(observability, "log_level", "observability"),
                trace_enabled=_require_bool(observability, "trace_enabled", "observability"),
                trace_file=_require_str(observability, "trace_file", "observability"),
                structured_logging=_require_bool(observability, "structured_logging", "observability"),
            ),
            ingestion=ingestion_settings,
            vision_llm=vision_llm_settings,
            answer_generator=answer_generator_settings,
            prompts=prompts_settings,
        )

        return settings


def validate_settings(settings: Settings) -> None:
    """Validate settings and raise SettingsError if invalid."""

    if not settings.llm.provider:
        raise SettingsError("Missing required field: llm.provider")
    if not settings.embedding.provider:
        raise SettingsError("Missing required field: embedding.provider")
    if not settings.vector_store.provider:
        raise SettingsError("Missing required field: vector_store.provider")
    if not settings.retrieval.rrf_k:
        raise SettingsError("Missing required field: retrieval.rrf_k")
    if not settings.rerank.provider:
        raise SettingsError("Missing required field: rerank.provider")
    if not settings.evaluation.provider:
        raise SettingsError("Missing required field: evaluation.provider")
    if not settings.observability.log_level:
        raise SettingsError("Missing required field: observability.log_level")


# Environment variable → dotted settings path whitelist.
# Only security-sensitive / commonly-tweaked keys are mapped; everything else
# keeps its YAML value. Extend for Phase 6, e.g. "AGENT_ENABLED": "agent.enabled".
_ENV_OVERRIDES: Dict[str, str] = {
    "LLM_API_KEY": "llm.api_key",
    "LLM_BASE_URL": "llm.base_url",
    "LLM_MODEL": "llm.model",
    "EMBEDDING_API_KEY": "embedding.api_key",
    "EMBEDDING_BASE_URL": "embedding.base_url",
    "EMBEDDING_MODEL": "embedding.model",
    "VISION_API_KEY": "vision_llm.api_key",
    "VISION_BASE_URL": "vision_llm.base_url",
}


def _set_nested(data: Dict[str, Any], dotted: str, value: str) -> None:
    """Write *value* into *data* at the given ``a.b.c`` path, creating dicts as needed."""
    keys = dotted.split(".")
    node: Any = data
    for key in keys[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[keys[-1]] = value


def _apply_env_overrides(data: Dict[str, Any], environ: Mapping[str, str]) -> Dict[str, Any]:
    """Merge whitelisted env vars into a raw YAML mapping (env wins over YAML).

    Only non-blank values override, so an empty/unset env var leaves the YAML
    value untouched.  Overrides are applied only to top-level sections already
    present in the YAML: an env var must never *resurrect* a section that the
    config omits, because that partial section would then fail validation
    (e.g. ``VISION_API_KEY`` on a config without a ``vision_llm`` block must
    not turn into ``vision_llm: {api_key: ...}`` and raise
    ``Missing required field: vision_llm.enabled``).
    """
    for env_name, dotted_path in _ENV_OVERRIDES.items():
        value = environ.get(env_name)
        if value is None or not value.strip():
            continue
        section = dotted_path.split(".")[0]
        if section not in data or not isinstance(data[section], dict):
            continue
        _set_nested(data, dotted_path, value.strip())
    return data


def load_settings(path: str | Path | None = None, *, env_file: Path | None = None) -> Settings:
    """Load settings from a YAML file and validate required fields.

    Before parsing YAML, an optional ``.env`` file is loaded into the process
    environment (when present) so the whitelisted env overrides below can apply.
    Precedence: process environment > ``.env`` file > ``settings.yaml``.

    Args:
        path: Path to settings YAML.  Defaults to
            ``<repo>/config/settings.yaml`` (absolute, CWD-independent).
        env_file: Path to a ``.env`` file to load.  Defaults to
            ``<repo>/config/.env``; pass ``None`` explicitly to skip loading.
    """
    env_path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if env_path.exists():
        # override=False: an already-set process env var wins over the .env file.
        load_dotenv(dotenv_path=env_path, override=False)

    settings_path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    if not settings_path.is_absolute():
        settings_path = resolve_path(settings_path)
    if not settings_path.exists():
        raise SettingsError(f"Settings file not found: {settings_path}")

    with settings_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    data = _apply_env_overrides(data or {}, os.environ)
    settings = Settings.from_dict(data)
    validate_settings(settings)
    return settings
