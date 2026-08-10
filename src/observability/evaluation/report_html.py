"""Render evaluation reports as self-contained HTML (no external assets).

Pure functions that turn an ``EvalReport.to_dict()`` / ablation dict into a
single HTML page with inline CSS.  No third-party dependencies; all user text
is escaped with :func:`html.escape`.
"""

from __future__ import annotations

import html
import json
from typing import Any

_PAGE_CSS = """
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       margin: 2rem auto; max-width: 1000px; color: #1f2933; line-height: 1.5; }
h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
h2 { font-size: 1.1rem; margin-top: 1.6rem; border-bottom: 1px solid #e4e7eb;
     padding-bottom: .3rem; }
table { border-collapse: collapse; margin: .75rem 0; width: 100%; }
th, td { border: 1px solid #e4e7eb; padding: .4rem .6rem; text-align: left;
         font-size: .9rem; }
th { background: #f5f7fa; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.muted { color: #7b8794; }
.meta td { border: none; padding: .15rem .6rem .15rem 0; }
details { margin: .5rem 0; }
summary { cursor: pointer; font-weight: 600; }
pre { background: #f5f7fa; padding: .75rem; border-radius: 4px;
      overflow-x: auto; font-size: .85rem; }
"""


def _esc(value: Any) -> str:
    """Escape a value for safe HTML embedding."""
    return html.escape(str(value))


def _metric_rows(metrics: dict[str, float]) -> str:
    """Render a metrics dict as table rows."""
    if not metrics:
        return '<tr><td colspan="2" class="muted">(no metrics)</td></tr>'
    return "".join(
        f"<tr><td>{_esc(k)}</td><td class='num'>{v:.4f}</td></tr>"
        for k, v in sorted(metrics.items())
    )


def _page(title: str, body: str) -> str:
    """Wrap body in the shared HTML skeleton."""
    return (
        "<!doctype html>\n<html lang='zh'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_PAGE_CSS}</style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def render_report_html(report: dict[str, Any]) -> str:
    """Render a single evaluation report dict to an HTML page."""
    meta_fields = [
        ("run_id", report.get("run_id", "—")),
        ("timestamp", report.get("timestamp", "—")),
        ("evaluator", report.get("evaluator_name", "—")),
        ("test_set", report.get("test_set_path", "—")),
        ("collection", report.get("collection", "—")),
        ("variant", report.get("variant", "—")),
        ("query_count", report.get("query_count", 0)),
        ("total_elapsed_ms", f"{report.get('total_elapsed_ms', 0):.0f} ms"),
    ]
    meta_html = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in meta_fields
    )

    agg = report.get("aggregate_metrics", {})
    agg_html = _metric_rows(agg)

    query_html = ""
    for idx, qr in enumerate(report.get("query_results", []), 1):
        metrics_html = _metric_rows(qr.get("metrics", {}))
        retrieved = qr.get("retrieved_chunk_ids", [])
        retrieved_html = (
            _esc(", ".join(retrieved)) if retrieved else '<span class="muted">(none)</span>'
        )
        answer = qr.get("generated_answer")
        answer_html = f"<p><strong>Answer:</strong> {_esc(answer)}</p>" if answer else ""
        query_html += (
            f"<details><summary>Q{idx}: {_esc(qr.get('query', '—'))} "
            f"<span class='muted'>({qr.get('elapsed_ms', 0):.0f} ms)</span></summary>\n"
            f"<table>\n{metrics_html}\n</table>\n"
            f"<p><strong>Retrieved chunks:</strong> {retrieved_html}</p>\n"
            f"{answer_html}\n"
            "</details>\n"
        )

    config = report.get("config_snapshot", {})
    config_html = (
        f"<pre>{_esc(json.dumps(config, indent=2, ensure_ascii=False))}</pre>"
        if config
        else '<p class="muted">(no config snapshot)</p>'
    )

    body = (
        f"<h1>Evaluation Report</h1>\n"
        f"<table class='meta'>\n{meta_html}\n</table>\n"
        f"<h2>Aggregate Metrics</h2>\n<table>\n{agg_html}\n</table>\n"
        f"<h2>Per-Query Results</h2>\n{query_html}\n"
        f"<h2>Config Snapshot</h2>\n{config_html}\n"
    )
    return _page("Evaluation Report", body)


def render_ablation_html(ablation: dict[str, Any]) -> str:
    """Render an ablation dict to an HTML page with a metric×variant matrix."""
    variants = ablation.get("variants", {})
    variant_names = list(variants.keys())
    comparison = ablation.get("comparison", {})

    if comparison and variant_names:
        header = (
            "<tr><th>metric</th>"
            + "".join(f"<th>{_esc(name)}</th>" for name in variant_names)
            + "</tr>"
        )
        rows = ""
        for metric, values in comparison.items():
            cells = "".join(
                f"<td class='num'>{values.get(name, 0.0):.4f}</td>"
                for name in variant_names
            )
            rows += f"<tr><td>{_esc(metric)}</td>{cells}</tr>\n"
        matrix = f"<table>\n{header}\n{rows}</table>\n"
    else:
        matrix = '<p class="muted">(no comparison data)</p>'

    sections = ""
    for name, report in variants.items():
        agg = report.get("aggregate_metrics", {})
        agg_html = _metric_rows(agg)
        sections += (
            f"<details open><summary>Variant: {_esc(name)}</summary>\n"
            f"<table>\n{agg_html}\n</table>\n</details>\n"
        )

    body = (
        "<h1>Ablation Report</h1>\n"
        f"<p class='muted'>run_id: {_esc(ablation.get('run_id', '—'))} · "
        f"generated_at: {_esc(ablation.get('generated_at', '—'))}</p>\n"
        "<h2>Metric × Variant Comparison</h2>\n"
        f"{matrix}\n"
        "<h2>Per-Variant Detail</h2>\n"
        f"{sections}\n"
    )
    return _page("Ablation Report", body)
