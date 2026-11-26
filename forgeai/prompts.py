"""Loads prompt templates from /prompts. Placeholders use {{name}} so JSON braces stay literal."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def _raw(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def render(name: str, **vars) -> str:
    text = _raw(name)
    for k, v in vars.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def messages(name: str, system: str | None = None, **vars) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": render(name, **vars)})
    return msgs
