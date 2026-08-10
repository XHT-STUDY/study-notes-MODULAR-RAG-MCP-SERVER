"""Document versioning and content snapshots (Phase 4).

Provides :class:`DocumentVersionStore` which tracks which content hash is
active per document and stores content snapshots used for rollback.
"""

from src.ingestion.versioning.version_store import DocumentVersionStore

__all__ = ["DocumentVersionStore"]
