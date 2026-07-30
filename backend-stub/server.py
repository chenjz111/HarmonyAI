"""
HarmonyAI 后端 Stub Server — Sprint 2
5个 Agent 接口，格式完全对齐蔡子鑫的后端定义 (agent_stubs.py)
路由前缀: /api/v1
返回格式: Universal Shell envelope

运行方式：
    1. pip install fastapi uvicorn pydantic
    2. python server.py
    3. 访问 http://localhost:8000/docs

5个接口：
    POST /api/v1/assessment   -> Agent 1 评估  问卷 -> 健康画像
    POST /api/v1/diagnosis    -> Agent 2 辨证  画像 -> 证型诊断
    POST /api/v1/prescription -> Agent 3 处方  证型 -> 音乐处方
    POST /api/v1/generation   -> Agent 4 生成  处方 -> 音频
    POST /api/v1/feedback     -> Agent 5 反馈  评分 -> 决策
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import random

app = FastAPI(
    title="HarmonyAI Backend Stub",
    version="2.0.0",
    description="5 Agent 独立端点 - 格式对齐蔡子鑫后端 agent_stubs.py",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _run_id(agent):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    n = random.randint(100, 999)
    return f"run_{ts}_{agent}_{n}"


def _session_id():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    n = random.randint(1000, 9999)
    return f"sess_{ts}_{n}"


def make_envelope(
    agent_id, agent_name, agent_layer,
    run_id, session_id, user_id,
    status, confidence, reason, warnings,
    input_data, output_data,
):
    """构建 Universal Shell envelope — 与蔡子鑫 agent_stubs.py 完全一致"""
    return {
        "agent_id": agent_id,
        "agent_version": "1.0.0",
        "agent_name": agent_name,
        "agent_layer": agent_layer,
        "run_id": run_id,
        "session_id": session_id,
        "user_id": user_id,
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "warnings": warnings,
        "input": input_data,
        "output": output_data,
        "processing_time_ms": random.randint(100, 500),
        "timestamp": _now_iso(),
        "retry_count": 0,
    }


# ---------------------------------------------------------------------------
# 五行五音映射表
# ---------------------------------------------------------------------------

EMOTION_TONE_MAP = {
    "nu": {
        "tone_id": "jiao", "tone_name": "角调式", "element": "木", "organ": "肝",
        "emotion": "怒", "emotion_cn": "怒", "syndrome": "肝郁化火",
        "instruments": ["古筝", "古琴"], "bpm": 68, "note": "Mi",
    },
    "xi": {
        "tone_id": "zhi", "tone_name": "徵调式", "element": "火", "organ": "心",
        "emotion": "喜", "emotion_cn": "喜", "syndrome": "心火旺盛",
        "instruments": ["笛子", "唢呐"], "bpm": 72, "note": "Sol",
    },
    "si": {
        "tone_id": "gong", "tone_name": "宫调式", "element": "土", "organ": "脾",
        "emotion": "思", "emotion_cn": "思", "syndrome": "脾虚湿困",
        "instruments": ["埙", "笙"], "bpm": 64, "note": "Do",
    },
    "bei": {
        "tone_id": "shang", "tone_name": "商调式", "element": "金", "organ": "肺",
        "emotion": "悲", "emotion_cn": "悲", "syndrome": "肺气不足",
        "instruments": ["编钟", "锣"], "bpm": 60, "note": "Re",
    },
    "kong": {
        "tone_id": "yu", "tone_name": "羽调式", "element": "水", "organ": "肾",
        "emotion": "恐", "emotion_cn": "恐", "syndrome": "肾阳不足",
        "instruments": ["古琴", "鼓"], "bpm": 56, "note": "La",
    },
}

# 中文情绪 -> key
EMOTION_KEY_MAP = {"怒": "nu", "喜": "xi", "思": "si", "悲": "bei", "恐": "kong"}

# 五行 -> key
ELEMENT_KEY_MAP = {"木": "nu", "火": "xi", "土": "si", "金": "bei", "水": "kong"}


def get_tone_info_by_emotion(emotion_cn):
    key = EMOTION_KEY_MAP.get(emotion_cn, "nu")
    return EMOTION_TONE_MAP[key]


def get_tone_info_by_element(element):
    key = ELEMENT_KEY_MAP.get(element, "nu")
    return EMOTION_TONE_MAP[key]


# ---------------------------------------------------------------------------
# Agent 1 — 评估  POST /api/v1/assessment
# ---------------------------------------------------------------------------

@app.post("/api/v1/assessment", summary="Agent 1 — 评估Agent")
async def assessment(body: dict):
    """接收问卷 -> AI评估 -> 返回健康画像 envelope"""
    session_id = body.get("session_id", _session_id())
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", _run_id("eval"))
    emotion_scores = body.get("emotion_scores", {})

    has_input = bool(emotion_scores)
    emotion_cn = ""
    if isinstance(emotion_scores, dict):
        emotion_cn = emotion_scores.get("emotion", "")

    envelope = make_envelope(
        agent_id="evaluation_agent",
        agent_name="评估Agent",
        agent_layer="medical_analysis",
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        status="success" if has_input else "degraded",
        confidence=0.85 if has_input else 0.3,
        reason=["stub：使用提交的情绪评分"] if has_input else ["stub：输入为空，使用保守降级结果"],
        warnings=[] if has_input else ["输入不足，建议补充问卷"],
        input_data={"emotion_scores": emotion_scores},
        output_data={"emotion_profile": emotion_scores},
    )
    return envelope


# ---------------------------------------------------------------------------
# Agent 2 — 辨证  POST /api/v1/diagnosis
# ---------------------------------------------------------------------------

@app.post("/api/v1/diagnosis", summary="Agent 2 — 中医辨证Agent")
async def diagnosis(body: dict):
    """接收健康画像 -> AI辨证 -> 返回证型诊断 envelope"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", _run_id("diag"))
    assessment_envelope = body.get("assessment", body.get("assessment_result", {}))

    if not session_id:
        return {"detail": "session_id is required"}, 400

    confidence = float(assessment_envelope.get("confidence", 0.85))

    # 从评估结果获取情绪，推断证型
    emotion_profile = assessment_envelope.get("output", {}).get("emotion_profile", {})
    if isinstance(emotion_profile, dict):
        emotion_cn = emotion_profile.get("emotion", "怒")
    else:
        emotion_cn = "怒"

    info = get_tone_info_by_emotion(emotion_cn)

    envelope = make_envelope(
        agent_id="diagnosis_agent",
        agent_name="辨证Agent",
        agent_layer="medical_analysis",
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        status="success" if confidence >= 0.4 else "degraded",
        confidence=confidence,
        reason=[f"stub：{emotion_cn}情绪映射为{info['syndrome']}"],
        warnings=[] if confidence >= 0.4 else ["上游输入可信度不足"],
        input_data={"assessment": assessment_envelope.get("output", {})},
        output_data={
            "syndrome_diagnosis": {
                "primary": {
                    "name": info["syndrome"],
                    "element": info["element"],
                    "organ": info["organ"],
                    "emotion": info["emotion_cn"],
                    "severity_level": 3,
                    "severity_name": "中度",
                }
            },
            "search_keywords": [info["syndrome"], info["tone_name"], "疏肝解郁"],
        },
    )
    return envelope


# ---------------------------------------------------------------------------
# Agent 3 — 处方  POST /api/v1/prescription
# ---------------------------------------------------------------------------

@app.post("/api/v1/prescription", summary="Agent 3 — 音乐处方Agent")
async def prescription(body: dict):
    """接收证型 -> AI生成处方 -> 返回音乐处方 envelope"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", _run_id("rx"))
    diagnosis_envelope = body.get("diagnosis", body.get("diagnosis_result", {}))

    if not session_id:
        return {"detail": "session_id is required"}, 400

    confidence = float(diagnosis_envelope.get("confidence", 0.77))

    # 从诊断结果获取五行，找音调
    sd = diagnosis_envelope.get("output", {}).get("syndrome_diagnosis", {})
    primary = sd.get("primary", {})
    element = primary.get("element", "木")

    info = get_tone_info_by_element(element)
    syndrome_name = primary.get("name", info["syndrome"])

    envelope = make_envelope(
        agent_id="prescription_agent",
        agent_name="处方Agent",
        agent_layer="knowledge_mapping",
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        status="success",
        confidence=confidence,
        reason=[f"stub：{syndrome_name}对应{info['tone_name']}、{info['bpm']}BPM与{info['instruments'][0]}"],
        warnings=[],
        input_data={"diagnosis": diagnosis_envelope.get("output", {})},
        output_data={
            "music_feature": {
                "tone_id": info["tone_id"],
                "tone_name": info["tone_name"],
                "bpm": info["bpm"],
                "instruments": info["instruments"],
            },
            "prompt_template": {
                "template_id": "CN_V1",
                "template_version": "1.0.0",
                "parameters": {
                    "duration": 15,
                    "bpm": info["bpm"],
                    "tone": info["tone_name"],
                },
            },
            "rendered_prompt": f"{info['instruments'][0]}独奏，{info['tone_name']}，BPM {info['bpm']}，舒缓宁静",
        },
    )
    return envelope


# ---------------------------------------------------------------------------
# Agent 4 — 生成  POST /api/v1/generation
# ---------------------------------------------------------------------------

@app.post("/api/v1/generation", summary="Agent 4 — 音乐生成Agent")
async def generation(body: dict):
    """接收处方 -> AI生成 -> 返回音频 envelope"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", _run_id("gen"))
    prescription_envelope = body.get("prescription", body.get("prescription_result", {}))

    if not session_id:
        return {"detail": "session_id is required"}, 400

    confidence = float(prescription_envelope.get("confidence", 0.71))

    envelope = make_envelope(
        agent_id="generation_agent",
        agent_name="生成Agent",
        agent_layer="ai_generation",
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        status="degraded",
        confidence=confidence,
        reason=["stub：使用本地曲库示例音频，未调用外部生成服务"],
        warnings=["当前为 Sprint 2 本地曲库 stub"],
        input_data={"prescription": prescription_envelope.get("output", {})},
        output_data={
            "audio": {
                "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "format": "mp3",
            }
        },
    )
    return envelope


# ---------------------------------------------------------------------------
# Agent 5 — 反馈  POST /api/v1/feedback
# ---------------------------------------------------------------------------

@app.post("/api/v1/feedback", summary="Agent 5 — 用户反馈Agent")
async def feedback(body: dict):
    """接收反馈 -> AI决策 -> 返回 continue/adjust/rediag"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", _run_id("fb"))
    generation_envelope = body.get("generation", body.get("generation_result", {}))
    satisfaction = body.get("overall_satisfaction", 4)

    if not session_id:
        return {"detail": "session_id is required"}, 400

    # 根据评分决定 action
    if satisfaction >= 4:
        action = "continue"
        next_step = "push_next_day"
        reason_text = f"stub：用户评分{satisfaction}分，继续当前方案"
    elif satisfaction >= 2:
        action = "adjust"
        next_step = "adjust_prescription"
        reason_text = f"stub：用户评分{satisfaction}分，调整处方参数"
    else:
        action = "rediag"
        next_step = "restart_diagnosis"
        reason_text = f"stub：用户评分{satisfaction}分，建议重新辨证"

    envelope = make_envelope(
        agent_id="feedback_agent",
        agent_name="反馈Agent",
        agent_layer="ai_generation",
        run_id=run_id,
        session_id=session_id,
        user_id=user_id,
        status="success",
        confidence=0.8,
        reason=[reason_text],
        warnings=[],
        input_data={"audio": generation_envelope.get("output", {}).get("audio", {})},
        output_data={
            "decision": {
                "action": action,
                "next_step": next_step,
            }
        },
    )
    return envelope


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"app": "HarmonyAI", "version": "2.0.0", "docs": "/docs"}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "timestamp": _now_iso()}


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("HarmonyAI 后端 Stub (Sprint 2) 启动中...")
    print("=" * 50)
    print("5个 Agent 接口：")
    print("  POST /api/v1/assessment   - Agent 1 评估")
    print("  POST /api/v1/diagnosis    - Agent 2 辨证")
    print("  POST /api/v1/prescription - Agent 3 处方")
    print("  POST /api/v1/generation   - Agent 4 生成")
    print("  POST /api/v1/feedback     - Agent 5 反馈")
    print("=" * 50)
    print("接口文档：http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
