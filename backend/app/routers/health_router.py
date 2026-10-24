"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check():
    """Returns server health status. Used for Docker healthcheck and monitoring."""
    return {"status": "healthy", "service": "HarmonyAI"}
