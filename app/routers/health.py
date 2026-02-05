"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint (public, no authentication required).

    Returns:
        A dict with status "ok".
    """
    return {"status": "ok"}
