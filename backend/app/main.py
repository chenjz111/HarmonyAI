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
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import init_database
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
    workflow_v2_router,
)
from backend.app.routers.v3 import auth_router as auth_v3_router
from backend.app.routers.v3 import feedback_router as feedback_v3_router
from backend.app.routers.v3 import generation_router as generation_v3_router
from backend.app.routers.v3 import session_router as session_v3_router
from backend.app.routers.v3 import understanding_router as understanding_v3_router
from backend.app.routers.v3 import questionnaire_router as questionnaire_v3_router
from backend.app.routers.v3 import document_router as document_v3_router
from backend.app.routers.v3 import document_set_router as document_set_v3_router
from backend.app.routers.v3 import document_relevance_router as document_relevance_v3_router
from backend.app.routers.v3.transport import V3APIError, v3_api_error_handler


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Ensure the portable local schema is ready before serving requests."""
    init_database()
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description=(
        "五音疗愈平台 —— 基于中医五音理论的 AI 音乐辅助调理系统\n\n"
        "## Sprint 3 — Competition Version\n"
        "| 端点 | 说明 |\n"
        "|------|------|\n"
        "| `/api/v2/assessments` | 多源状态评估 |\n"
        "| `/api/v2/workflows` | 五 Agent 统一工作流 |\n"
        "| `/api/v2/music` | 本地曲库匹配 |\n"
        "| `/api/v2/sessions` | 会话管理 |\n"
        "| `/api/v2/documents` | 病例上传 |\n"
        "| `/api/v2/feedback` | Feedback 2.0 (pre/post) |\n\n"
        "### V1 兼容端点\n"
        "| `/api/v1/assessment` | 1 评估 | 问卷 → 健康画像 |\n"
        "| `/api/v1/diagnosis` | 2 辨证 | 画像 → 证型诊断 |\n"
        "| `/api/v1/prescription` | 3 处方 | 证型 → 音乐处方 |\n"
        "| `/api/v1/generation` | 4 生成 | 处方 → 音频 |\n"
        "| `/api/v1/feedback` | 5 反馈 | 评分 → 决策 |"
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
app.include_router(feedback_router.router, prefix="/api/v1", tags=["Agent 5 — 反馈"])
app.include_router(feedback_router.v2_router, prefix="/api/v2", tags=["Agent 5 — 反馈 V2"])
app.include_router(document_router.router, prefix="/api/v2", tags=["Sprint 3 — 文档上传"])
app.include_router(session_router.router, prefix="/api/v2", tags=["Sprint 3 — 会话"])
app.include_router(provider_router.router, prefix="/api/v2", tags=["Sprint 4 — Provider 健康检查"])
app.include_router(assessment_v2_router.router, prefix="/api/v2", tags=["Sprint 4 — Assessment V2"])
app.include_router(workflow_v2_router.router, prefix="/api/v2", tags=["Sprint 3 — 工作流"])
app.include_router(auth_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Auth"])
app.include_router(session_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Session"])
app.include_router(understanding_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Understanding"])
app.include_router(questionnaire_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Questionnaire"])
app.include_router(document_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Document"])
app.include_router(document_set_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Document Set"])
app.include_router(document_relevance_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Document Relevance"])
app.include_router(generation_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Music Generation"])
app.include_router(feedback_v3_router.router, prefix="/api/v3", tags=["Sprint 5 — V3 Feedback"])
app.add_exception_handler(V3APIError, v3_api_error_handler)


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
