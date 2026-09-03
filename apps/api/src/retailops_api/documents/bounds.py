"""Application-side size and page bounds for document intake."""

from retailops_api.core.limits import (
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_MAX_TEXTRACT_SYNC_PAGES,
    DEFAULT_MAX_UPLOAD_BYTES,
    DocumentBounds,
)

__all__ = [
    "DEFAULT_MAX_PROMPT_CHARS",
    "DEFAULT_MAX_TEXTRACT_SYNC_PAGES",
    "DEFAULT_MAX_UPLOAD_BYTES",
    "DocumentBounds",
]
