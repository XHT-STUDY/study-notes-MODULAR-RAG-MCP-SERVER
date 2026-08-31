"""Human-readable ingestion pipeline report.

Builds the detailed stage-by-stage report for one ingested file from the
pipeline's :class:`PipelineResult` and the request :class:`TraceContext`.
Every pipeline stage is listed with its inputs, outputs and elapsed time,
including the per-chunk intermediate state (chunking results, LLM
refine/enrich before-after, BM25 term statistics, vector-ID mapping).
Shared by ``scripts/ingest.py`` (prints to console) and the dashboard
ingestion manager (renders in the UI and mirrors to the server console).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.settings import Settings
from src.core.trace.trace_context import TraceContext
from src.ingestion.pipeline import PipelineResult

_LINE = "=" * 68
_THIN = "-" * 68
_PREVIEW_WIDTH = 64
TERMS_PREVIEW = 5
TOTAL_STAGES = 6


def _fmt_ms(ms: float | None) -> str:
    """Format milliseconds as '12.3 ms' or '1.23 s'."""
    if ms is None:
        return "-"
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    return f"{ms:.1f} ms"


def _short(text: Any, width: int = _PREVIEW_WIDTH) -> str:
    """One-line text preview (truncated)."""
    flat = " ".join(str(text or "").split())
    if len(flat) <= width:
        return flat
    return flat[:width] + "…"


def _stage(trace: TraceContext, name: str) -> tuple[dict[str, Any] | None, float | None]:
    """Return (data, elapsed_ms) recorded for a trace stage."""
    for entry in reversed(trace.stages):
        if entry.get("stage") == name:
            return entry.get("data") or {}, entry.get("elapsed_ms")
    return None, None


def _file_size_label(path: str) -> str:
    try:
        size = Path(path).stat().st_size
        if size >= 1024 * 1024:
            return f" ({size / 1024 / 1024:.1f} MB)"
        return f" ({size / 1024:.1f} KB)"
    except OSError:
        return ""


def _print_stage_header(lines: list[str], index: int, title: str,
                        elapsed_ms: float | None, status: str = "执行") -> None:
    timing = f"    耗时 {_fmt_ms(elapsed_ms)}" if status == "执行" else ""
    lines.append("")
    lines.append(_THIN)
    lines.append(f" [{index}/{TOTAL_STAGES}] {title}   <{status}>{timing}")
    lines.append(_THIN)


def _print_io(lines: list[str], label: str, items: list[str]) -> None:
    lines.append(f" {label}:")
    for item in items:
        lines.append(f"   {item}")


def build_file_report(
    result: PipelineResult,
    trace: TraceContext,
    settings: Settings,
    collection: str,
    title: str,
) -> str:
    """Build the detailed stage-by-stage report text for one ingested file.

    Args:
        result: Result returned by ``IngestionPipeline.run``.
        trace: The trace context passed to ``run`` (stage details + timings).
        settings: Loaded application settings (used for model/chunker labels).
        collection: Collection name the file was ingested into.
        title: Report title line, e.g. ``"[1/3] 摄取报告 · report.pdf"``.

    Returns:
        Multi-line report string (no trailing newline).
    """
    lines: list[str] = []
    add = lines.append

    add(_LINE)
    add(f" {title}")
    add(_LINE)

    if not result.success:
        add(f" [FAIL] {result.error}")
        reached = [s for s in ("integrity", "loading", "chunking", "transform", "encoding", "storage")
                   if s in result.stages]
        if reached:
            add(f" 已完成阶段: {', '.join(reached)}")
        return "\n".join(lines)

    integrity = result.stages.get("integrity", {})
    if integrity.get("skipped"):
        add(f" <跳过> 文件未变化，已处理过（hash={str(integrity.get('file_hash', ''))[:16]}…）")
        add(" 提示   : 如需强制重新摄取，加 --force")
        return "\n".join(lines)

    ing = getattr(settings, "ingestion", None)
    emb_cfg = getattr(settings, "embedding", None)

    # ── Stage 1: integrity ────────────────────────────────────────────
    _print_stage_header(lines, 1, "完整性检查 · SHA256", integrity.get("elapsed_ms"))
    _print_io(lines, "输入", [
        f"file = {result.file_path}{_file_size_label(result.file_path)}",
        f"collection = {collection}",
    ])
    _print_io(lines, "输出", [
        f"hash = {str(integrity.get('file_hash', ''))[:16]}…  → 新文件，需要处理",
    ])

    # ── Stage 2: loading ──────────────────────────────────────────────
    load, load_ms = _stage(trace, "load")
    if load:
        _print_stage_header(lines, 2, f"文档加载 · PdfLoader ({load.get('method', 'markitdown')})", load_ms)
        _print_io(lines, "输入", ["file(解析 PDF → 纯文本 + 图片提取)"])
        _print_io(lines, "输出", [
            f"doc_id = {load.get('doc_id', '?')}",
            f"text = {load.get('text_length', 0)} chars    images = {load.get('image_count', 0)}",
            f"预览: {_short(load.get('text_preview', ''))}",
        ])

    # ── Stage 3: chunking ─────────────────────────────────────────────
    split, split_ms = _stage(trace, "split")
    if split:
        chunk_size = getattr(ing, "chunk_size", "?") if ing else "?"
        overlap = getattr(ing, "chunk_overlap", "?") if ing else "?"
        splitter = getattr(ing, "splitter", "recursive") if ing else "recursive"
        _print_stage_header(
            lines, 3, f"分块 · {splitter} (chunk_size={chunk_size}, overlap={overlap})", split_ms)
        chunks = split.get("chunks", [])
        _print_io(lines, "输入", [
            f"document = {load.get('doc_id', '?')} ({load.get('text_length', 0)} chars)",
        ])
        out = [
            f"chunks = {split.get('chunk_count', 0)}    "
            f"平均长度 = {split.get('avg_chunk_size', 0)} chars",
        ]
        _print_io(lines, "输出", out)
        for i, c in enumerate(chunks):
            lines.append(
                f"   #{i:02d}  {c.get('chunk_id', '?')}  "
                f"{c.get('char_len', 0)} chars  {_short(c.get('text', ''))}"
            )

    # ── Stage 4: transforms ───────────────────────────────────────────
    transform, transform_ms = _stage(trace, "transform")
    if transform:
        _print_stage_header(lines, 4, "LLM 变换 · 精炼 → 元数据增强 → 图像描述", transform_ms)
        tf = result.stages.get("transform", {})
        t_chunks = transform.get("chunks", [])
        refiner = tf.get("chunk_refiner", {})
        enricher = tf.get("metadata_enricher", {})
        captioner = tf.get("image_captioner", {})

        # 4a refine: before → after per chunk
        lines.append(f" 4a. 文本精炼 · ChunkRefiner    耗时 {_fmt_ms(tf.get('refine_ms'))}")
        _print_io(lines, "输入", [f"{len(t_chunks)} 个分块（原始文本）"])
        before_total = sum(len(c.get("text_before", "")) for c in t_chunks)
        after_total = sum(len(c.get("text_after", "")) for c in t_chunks)
        _print_io(lines, "输出", [
            f"LLM×{refiner.get('llm', 0)}  规则×{refiner.get('rule', 0)}"
            f"    总长度 {before_total} → {after_total} chars",
        ])
        for i, c in enumerate(t_chunks):
            lines.append(
                f"   #{i:02d}  {len(c.get('text_before', ''))}c→{len(c.get('text_after', ''))}c"
                f"  [{c.get('refined_by', '-') or '-'}]  {_short(c.get('text_after', ''))}"
            )

        # 4b enrich: generated metadata per chunk
        lines.append("")
        lines.append(f" 4b. 元数据增强 · MetadataEnricher    耗时 {_fmt_ms(tf.get('enrich_ms'))}")
        _print_io(lines, "输入", [f"{len(t_chunks)} 个精炼后的分块"])
        _print_io(lines, "输出", [
            f"LLM×{enricher.get('llm', 0)}  规则×{enricher.get('rule', 0)}"
            f"    每块生成 title / tags / summary:",
        ])
        for i, c in enumerate(t_chunks):
            lines.append(
                f"   #{i:02d}  [{c.get('enriched_by', '-') or '-'}] "
                f"title={_short(c.get('title', ''), 30)}  "
                f"tags={c.get('tags', []) or '[]'}"
            )
            summary = c.get("summary", "")
            if summary:
                lines.append(f"        └ summary: {_short(summary)}")

        # 4c caption
        lines.append("")
        lines.append(f" 4c. 图像描述 · ImageCaptioner    耗时 {_fmt_ms(tf.get('caption_ms'))}")
        vision = getattr(getattr(settings, "vision_llm", None), "enabled", False)
        _print_io(lines, "输入", [f"chunk 中引用的图片（vision_llm={'启用' if vision else '关闭'}）"])
        _print_io(lines, "输出", [f"带描述的分块 ×{captioner.get('captioned_chunks', 0)}"])

    # ── Stage 5: encoding ─────────────────────────────────────────────
    embed, embed_ms = _stage(trace, "embed")
    if embed:
        model = getattr(emb_cfg, "model", "?") if emb_cfg else "?"
        provider = getattr(emb_cfg, "provider", "?") if emb_cfg else "?"
        batch_size = getattr(ing, "batch_size", "?") if ing else "?"
        _print_stage_header(lines, 5, f"向量化 · {provider}/{model} (batch_size={batch_size})", embed_ms)
        _print_io(lines, "输入", [f"{embed.get('dense_vector_count', 0)} 个分块文本"])
        _print_io(lines, "输出", [
            f"dense = {embed.get('dense_vector_count', 0)} 条 × "
            f"{embed.get('dense_dimension', 0)} 维 (Embedding API)",
            f"sparse = {embed.get('sparse_doc_count', 0)} 条 BM25 词频统计（本地）:",
        ])
        for i, c in enumerate(embed.get("chunks", [])):
            terms = c.get("top_terms", [])[:TERMS_PREVIEW]
            top = ", ".join(f"{t.get('term', '')}×{t.get('freq', 0)}" for t in terms)
            lines.append(
                f"   #{i:02d}  dim={c.get('dense_dim', '?')}  "
                f"doc_len={c.get('doc_length', 0)}  unique_terms={c.get('unique_terms', 0)}"
                f"  top: {top}"
            )

    # ── Stage 6: storage ──────────────────────────────────────────────
    upsert, upsert_ms = _stage(trace, "upsert")
    if upsert:
        dense_store = upsert.get("dense_store", {})
        sparse_store = upsert.get("sparse_store", {})
        image_store = upsert.get("image_store", {})
        _print_stage_header(lines, 6, "入库 · Chroma + BM25 + 图像索引", upsert_ms)
        _print_io(lines, "输入", [
            f"{dense_store.get('count', 0)} dense 向量 + "
            f"{sparse_store.get('count', 0)} sparse 统计 + "
            f"{image_store.get('count', 0)} 图片",
        ])
        _print_io(lines, "输出", [
            f"chroma +{dense_store.get('count', 0)}  ({dense_store.get('path', '?')}, "
            f"collection={dense_store.get('collection', collection)})",
            f"bm25    +{sparse_store.get('count', 0)}  ({sparse_store.get('path', '?')})",
            f"images   {image_store.get('count', 0)}",
            "chunk → 向量 ID 映射:",
        ])
        for m in upsert.get("chunk_mapping", []):
            lines.append(f"   {m.get('chunk_id', '?')} → {m.get('vector_id', '?')}")

    # ── Summary ───────────────────────────────────────────────────────
    total_ms = trace.elapsed_ms()
    lines.append("")
    lines.append(_LINE)
    lines.append(
        f" [SUMMARY] {result.chunk_count} chunks, {result.image_count} images → 集合 '{collection}'"
        f"    总耗时 {_fmt_ms(total_ms)}"
    )
    lines.append(f"           doc_id = {result.doc_id}")
    return "\n".join(lines)
