"""HarmonyAI FastAPI Application — MVP Sprint 1.

3 consolidated API endpoints per mvp-definition.md:
  POST /api/assess       → Agent ①+② (questionnaire → assessment + diagnosis)
  GET  /api/prescription  → Agent ③+④ (syndrome → daily plan + audio)
  POST /api/feedback      → Agent ⑤   (rating → decision)

Start:
  cd HarmonyAI/
  set PYTHONPATH=.
  python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

Swagger: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.routers import (
    health_router,
    assess_router,
    prescription_router,
    feedback_router,
)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    description=(
        "五音疗愈平台 —— 基于中医五音理论的 AI 音乐辅助调理系统\n\n"
        "## MVP Sprint 1 端点\n"
        "| 端点 | 方法 | 说明 |\n"
        "|------|------|------|\n"
        "| `/api/assess` | POST | 提交问卷 → 返回评估+辨证 |\n"
        "| `/api/prescription` | GET | 获取音乐处方+音频 |\n"
        "| `/api/feedback` | POST | 提交反馈 → 返回决策 |\n\n"
        "## 设计原则\n"
        "- Schema 即合约（与 agent-schemas.md 严格一致）\n"
        "- Prompt 不入库（运行时组装）\n"
        "- 每层说自己的语言"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router.router, tags=["Health"])
app.include_router(assess_router.router, prefix="/api", tags=["MVP — 评估+辨证"])
app.include_router(prescription_router.router, prefix="/api", tags=["MVP — 处方+音频"])
app.include_router(feedback_router.router, prefix="/api", tags=["MVP — 反馈"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }
