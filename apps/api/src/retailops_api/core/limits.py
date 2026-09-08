"""Application bounds shared by config and document adapters.

Kept out of ``documents`` so ``AwsConfig`` can import them without a
package cycle through ``documents.__init__``.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DOCUMENTS_PREFIX = "supplier-documents"
LIVE_SMOKE_PREFIX = "block13"
DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_TEXTRACT_SYNC_PAGES = 5
DEFAULT_MAX_PROMPT_CHARS = 24_000

#: Largest request body accepted at the HTTP boundary, before any handler runs.
DEFAULT_MAX_REQUEST_BYTES = 6 * 1024 * 1024
#: Decisions a single principal may submit inside the window.
DEFAULT_DECISION_RATE_LIMIT = 30
DEFAULT_DECISION_RATE_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class DocumentBounds:
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_textract_sync_pages: int = DEFAULT_MAX_TEXTRACT_SYNC_PAGES
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS
