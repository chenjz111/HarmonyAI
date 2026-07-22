from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class TemplateNotFoundError(FileNotFoundError):
    """Raised when a versioned prompt template cannot be found."""


@dataclass(frozen=True)
class RenderedPrompt:
    template_id: str
    template_version: str
    text: str


class PromptEngine:
    def __init__(self, template_root: Path):
        self.template_root = Path(template_root)

    def render(self, template_id: str, params: Mapping[str, object]) -> RenderedPrompt:
        path = self.template_root / f"{template_id}.txt"
        if not path.is_file():
            raise TemplateNotFoundError(f"Prompt template not found: {template_id}")

        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        version_line = next((line for line in lines if line.startswith("template_version=")), None)
        if version_line is None:
            raise ValueError(f"Prompt template has no version: {template_id}")

        version = version_line.split("=", 1)[1].strip()
        body = "\n".join(line for line in lines if not line.startswith("template_version="))
        values = {
            "duration": 15,
            "bpm": 60,
            "tone": "宫调式",
            "style": "纯音乐",
            **dict(params),
        }
        return RenderedPrompt(template_id, version, body.format_map(values))
