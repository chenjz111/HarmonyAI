"""
HarmonyAI 后端 Stub Server
Sprint 1 验收专用：提供一个最小可运行的本地后端，让前端能真实发出 HTTP 请求。

运行方式：
    1. 安装依赖：pip install -r requirements.txt
    2. 启动服务：python server.py
    3. 服务启动后访问 http://localhost:8000/docs 查看接口文档

接口：
    POST   /api/assess                 提交问卷，返回评估结果
    GET    /api/prescription/{session_id}  根据会话 ID 获取处方
    POST   /api/feedback               提交播放反馈
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any
import random

app = FastAPI(title="HarmonyAI Backend Stub", version="0.1.0")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssessmentRequest(BaseModel):
    emotion: str
    tone: str
    answers: Dict[str, int]


class FeedbackRequest(BaseModel):
    rating: int
    session_id: str
    completed: bool = True


# 五音映射表
TONE_MAP = {
    "角": {"name": "角调", "instrument": "古筝", "syndrome": "肝郁化火"},
    "徵": {"name": "徵调", "instrument": "笛子", "syndrome": "心火旺盛"},
    "宫": {"name": "宫调", "instrument": "埙", "syndrome": "脾虚湿困"},
    "商": {"name": "商调", "instrument": "编钟", "syndrome": "肺气不足"},
    "羽": {"name": "羽调", "instrument": "古琴", "syndrome": "肾阳不足"},
}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _pick_tone(emotion: str, tone: str) -> str:
    """根据用户选择的情绪/音调返回主音。"""
    if tone and tone in TONE_MAP:
        return tone
    fallback = {"怒": "角", "喜": "徵", "思": "宫", "悲": "商", "恐": "羽"}
    return fallback.get(emotion, "角")


@app.post("/api/assess")
def assess(req: AssessmentRequest):
    """提交健康评估问卷，返回 AI 辨证结果。"""
    main_tone = _pick_tone(req.emotion, req.tone)
    info = TONE_MAP[main_tone]
    confidence = round(random.uniform(0.72, 0.88), 2)

    # 构造权重：主音占大头，其余按随机小权重补充
    tone_weights = {t: round(random.uniform(0.05, 0.15), 2) for t in TONE_MAP}
    tone_weights[main_tone] = round(random.uniform(0.55, 0.80), 2)
    # 归一化到 1.0
    total = sum(tone_weights.values())
    tone_weights = {k: round(v / total, 2) for k, v in tone_weights.items()}

    return {
        "session_id": f"stub-session-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}",
        "agent_id": "agent-1-assessment",
        "confidence": confidence,
        "timestamp": _now(),
        "emotion": req.emotion,
        "tone": req.tone,
        "syndrome": info["syndrome"],
        "recommended_tone": main_tone,
        "tone_weights": tone_weights,
        "reasoning": f"情绪以{req.emotion}为主，辨证属{info['syndrome']}，推荐{info['name']}{info['instrument']}调理。"
    }


@app.get("/api/prescription/{session_id}")
def get_prescription(session_id: str):
    """根据评估会话 ID 返回音乐处方（含音频 URL）。"""
    # 简单从 session_id 里推断音调，没有就随机
    main_tone = "角"
    for t in TONE_MAP:
        if t in session_id:
            main_tone = t
            break
    info = TONE_MAP[main_tone]
    tone_weight = round(random.uniform(0.55, 0.80), 2)

    return {
        "session_id": session_id,
        "agent_id": "agent-3-prescription",
        "confidence": round(random.uniform(0.75, 0.90), 2),
        "timestamp": _now(),
        "tone": main_tone,
        "tone_weight": tone_weight,
        "instrument": info["instrument"],
        "bpm": random.choice([60, 64, 68, 72]),
        "reasoning": f"{info['syndrome']} → {info['name']}疏肝理气，辅以宫调健脾安神",
        "prompt": f"{info['instrument']}独奏，{info['name']}，BPM 68，舒缓宁静",
        # 公开可访问的演示音频（非真实中医音乐，仅用于验证播放器）
        "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    }


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    """提交用户反馈。"""
    return {
        "success": True,
        "agent_id": "agent-5-feedback",
        "timestamp": _now(),
        "decision": "accepted",
        "session_id": req.session_id,
        "rating": req.rating
    }


@app.get("/")
def root():
    return {"message": "HarmonyAI backend stub is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    print("启动 HarmonyAI 后端 Stub...")
    print("接口文档：http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
