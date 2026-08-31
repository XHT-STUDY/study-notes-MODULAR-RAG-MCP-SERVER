"""Dashboard Module.

This package contains the Streamlit dashboard application.

Importing this package quiets the server console: raw pipeline run logs
would flood the terminal running Streamlit.  The per-ingest console output
is instead the clean stage report printed by the ingestion manager page,
and the same report is rendered in the UI.  WARNING+ logs from unrelated
components (e.g. the PyMuPDF image-extraction warning) stay visible.
"""

import logging

# jieba resets its logger to DEBUG at import time, so import it *before*
# silencing; otherwise its dictionary-loading messages leak on first use.
import jieba  # noqa: F401

logging.getLogger("src").setLevel(logging.WARNING)
logging.getLogger("jieba").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.WARNING)
# pdfminer (via markitdown) emits noisy FontBBox warnings on many Chinese
# PDFs; they carry no actionable information for this pipeline.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

__all__ = []
