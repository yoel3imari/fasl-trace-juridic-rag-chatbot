"""
Health check router.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Returns 200 OK when the service is running."""
    return {"status": "ok"}
