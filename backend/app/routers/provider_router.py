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
        providers = check_all_providers()
        return v2_ok({
            "providers": [{
                "name": p.name,
                "status": p.status,
                "type": p.provider_type,
                "message": p.message,
                "latency_ms": p.latency_ms,
            } for p in providers],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }, req_id)
    except Exception as e:
        return v2_err("HEALTH_CHECK_FAILED", str(e)[:200], req_id)
