"""Exception handling & degradation — agent-architecture.md Chapter 3.

Three levels:
  Level 1 — Retry (auto-retry up to 3 times)
  Level 2 — Degrade (fallback path, mark status=degraded)
  Level 3 — Fail+Alert (log, notify, return friendly error)
"""
from enum import Enum
from typing import Optional


class ErrorLevel(str, Enum):
    RETRY = "retry"       # Auto-retry recoverable errors
    DEGRADE = "degrade"   # Use fallback path
    FAIL = "fail"         # Blocking error


class AgentException(Exception):
    """Base exception for all Agent errors."""
    def __init__(
        self,
        agent_id: str,
        message: str,
        level: ErrorLevel = ErrorLevel.RETRY,
        error_code: str = "AGENT_ERROR",
        detail: Optional[dict] = None,
    ):
        self.agent_id = agent_id
        self.message = message
        self.level = level
        self.error_code = error_code
        self.detail = detail or {}
        super().__init__(message)


# ---------------------------------------------------------------------------
# Per-agent degradation strategies (Chapter 3.2)
# ---------------------------------------------------------------------------

class DegradationHandler:
    """Central degradation logic for all 5 Agents."""

    MAX_RETRIES = 3

    @staticmethod
    def handle(agent_id: str, exception: AgentException, retry_count: int) -> dict:
        """Return a degradation result dict for the given exception."""
        if retry_count < DegradationHandler.MAX_RETRIES:
            return {
                "status": "retry",
                "retry_count": retry_count + 1,
                "message": f"Retry {retry_count + 1}/{DegradationHandler.MAX_RETRIES}: {exception.message}",
            }

        # Max retries exceeded — degrade or skip
        strategies = {
            "evaluation_agent": {"fallback_status": "skipped", "message": "all input channels failed"},
            "diagnosis_agent":  {"fallback_status": "skipped", "message": "LLM + rule engine both failed"},
            "prescription_agent": {"fallback_status": "degraded", "message": "prescription degraded: using base weights"},
            "generation_agent":  {"fallback_status": "degraded", "message": "all music APIs down, fallback to local library"},
            "feedback_agent":    {"fallback_status": "degraded", "message": "feedback write failed, cached to Redis"},
        }

        strat = strategies.get(agent_id, {"fallback_status": "skipped", "message": "unknown agent"})
        return {
            "status": strat["fallback_status"],
            "retry_count": retry_count,
            "message": strat["message"],
            "degraded": strat["fallback_status"] == "degraded",
        }


# ---------------------------------------------------------------------------
# Concrete exception types
# ---------------------------------------------------------------------------

class UpstreamDegradedException(AgentException):
    """Warning passed when an upstream Agent ran degraded."""
    def __init__(self, agent_id: str, upstream_agent: str, reason: str):
        super().__init__(
            agent_id=agent_id,
            message=f"Upstream {upstream_agent} degraded: {reason}",
            level=ErrorLevel.DEGRADE,
            error_code="UPSTREAM_DEGRADED",
        )


class LLMTimeoutException(AgentException):
    def __init__(self, agent_id: str):
        super().__init__(agent_id=agent_id, message="LLM call timed out",
                         level=ErrorLevel.DEGRADE, error_code="LLM_TIMEOUT")


class APIFailureException(AgentException):
    def __init__(self, agent_id: str, provider: str):
        super().__init__(agent_id=agent_id, message=f"{provider} API call failed",
                         level=ErrorLevel.DEGRADE, error_code="API_FAILURE")
