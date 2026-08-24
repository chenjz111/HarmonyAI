"""Contract-safe transport helpers for public V3 routes."""

from typing import TypeVar
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.schemas.v3.envelope import (
    V3Error,
    V3ErrorEnvelope,
    V3SuccessEnvelope,
)


DataT = TypeVar("DataT", bound=BaseModel)


class V3APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        next_actions: list[str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.next_actions = next_actions or []


def _request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def v3_success(data: DataT) -> V3SuccessEnvelope[DataT]:
    return V3SuccessEnvelope[type(data)](data=data, request_id=_request_id())


async def v3_api_error_handler(
    _request: Request,
    error: V3APIError,
) -> JSONResponse:
    envelope = V3ErrorEnvelope(
        error=V3Error(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            next_actions=error.next_actions,
        ),
        request_id=_request_id(),
    )
    return JSONResponse(
        status_code=error.status_code,
        content=envelope.model_dump(mode="json"),
        headers={"WWW-Authenticate": "Bearer"}
        if error.status_code == 401
        else None,
    )
