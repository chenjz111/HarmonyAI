"""Shared polling helpers for the async Agent 4 generation API.

A real provider (Tencent Cloud TokenHub / minimax-music-v3.0) takes minutes to generate, so
the POST returns a queued task and the terminal outcome is observed through
GET /api/v3/music/generations/{task_id}.
"""

import time

TERMINAL_TASK_STATUSES = {"succeeded", "matched_fallback", "failed", "cancelled"}


def is_terminal_task(task: dict) -> bool:
    return task["status"] in TERMINAL_TASK_STATUSES


def poll_until(client, headers, task_id: str, predicate, *, timeout: float = 10.0):
    """Poll a generation task until ``predicate`` holds, returning the last task seen."""

    deadline = time.time() + timeout
    task = None
    while time.time() < deadline:
        response = client.get(
            f"/api/v3/music/generations/{task_id}", headers=headers
        )
        task = response.json()["data"]
        if predicate(task):
            return task
        time.sleep(0.05)
    return task
