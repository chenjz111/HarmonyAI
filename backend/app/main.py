"""HarmonyAI FastAPI Application — Sprint 3.

Sprint 3 adds:
  POST /api/v2/documents  → 病例上传(JPG/PNG/PDF)
  GET  /api/v2/documents/{session_id} → 查询文档
  POST /api/v2/documents/confirm → 确认/跳过
  Feedback 2.0 (backward compatible)

Start:
  cd HarmonyAI_repo/
  set PYTHONPATH=.
  python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

Swagger: http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.routers import (
    health_router,
    assessment_router,
    diagnosis_router,
    prescription_router,
    generation_router,
    feedback_router,
    document_router,
    session_router,
    provider_router,
    assessment_v2_router,
)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    description=(
        "五音疗愈平台 —— 基于中医五音理论的 AI 音乐辅助调理系统\n\n"
        "## Sprint 2 — 五 Agent 独立端点\n"
        "| 端点 | Agent | 说明 |\n"
        "|------|-------|------|\n"
        "| `/api/v1/assessment` | 1 评估 | 问卷 → 健康画像 |\n"
        "| `/api/v1/diagnosis` | 2 辨证 | 画像 → 证型诊断 |\n"
        "| `/api/v1/prescription` | 3 处方 | 证型 → 音乐处方 |\n"
        "| `/api/v1/generation` | 4 生成 | 处方 → 音频 |\n"
        "| `/api/v1/feedback` | 5 反馈 | 评分 → 决策 |\n\n"
        "每个端点返回 Universal Shell（agent-architecture.md 第 1 章）"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (demo audio for Sprint 2)
_static_dir = Path(__file__).resolve().parents[2] / "frontend" / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(health_router.router, tags=["Health"])
app.include_router(assessment_router.router, prefix="/api/v1", tags=["Agent 1 — 评估"])
app.include_router(diagnosis_router.router, prefix="/api/v1", tags=["Agent 2 — 辨证"])
app.include_router(prescription_router.router, prefix="/api/v1", tags=["Agent 3 — 处方"])
app.include_router(generation_router.router, prefix="/api/v1", tags=["Agent 4 — 生成"])
app.include_router(feedback_router.router, prefix="/api", tags=["Agent 5 — 反馈"])
app.include_router(document_router.router, prefix="/api/v2", tags=["Sprint 3 — 文档上传"])
app.include_router(session_router.router, prefix="/api/v2", tags=["Sprint 3 — 会话"])
app.include_router(provider_router.router, prefix="/api/v2", tags=["Sprint 4 — Provider 健康检查"])
app.include_router(assessment_v2_router.router, prefix="/api/v2", tags=["Sprint 4 — Assessment V2"])


@app.get("/", include_in_schema=False)
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
async def demo():
    """Serve the standalone demo page."""
    demo_path = Path(__file__).resolve().parents[2] / "frontend" / "demo.html"
    return demo_path.read_text(encoding="utf-8")


@app.get("/full-demo", response_class=HTMLResponse, include_in_schema=False)
async def full_demo():
    """Serve the full demo page (narrative + 30 questions + complete flow)."""
    demo_path = Path(__file__).resolve().parents[2] / "frontend" / "full-demo.html"
    return demo_path.read_text(encoding="utf-8")
