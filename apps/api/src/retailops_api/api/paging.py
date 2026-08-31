"""Shared offset-pagination checks for list endpoints."""

from fastapi import HTTPException

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def validate_page(limit: int, offset: int) -> tuple[int, int]:
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be at least 0")
    return limit, offset
