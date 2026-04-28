"""Placeholder FastAPI route definitions for the TriFirst API."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple health status response."""
    return {"status": "ok"}
