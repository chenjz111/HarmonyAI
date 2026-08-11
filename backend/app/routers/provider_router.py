"""Provider health check — Sprint 4: GET /api/v2/providers/health."""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter

from backend.app.core.provider_health import check_all_providers
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()


@router.get("/providers/health", summary="Sprint 4 — Provider 健康检查")
async def provider_health():
    """返回所有外部 Provider 的状态。"""
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    try:
        return v2_ok(check_all_providers(), req_id)
    except Exception:
        return v2_err(
            "HEALTH_CHECK_FAILED",
            "Provider 状态暂时不可用",
            req_id,
        )
