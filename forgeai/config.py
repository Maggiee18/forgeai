"""Run configuration. Everything can be set by env var, a forgeai.yaml file, or CLI flags."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    backend: str = "ollama"            # ollama | groq | openai | mock
    model: str = "qwen2.5:7b-instruct"  # factory model (intake, generator, eval generation, critic)
    # Committed demos: backend groq, model openai/gpt-oss-20b, judge_model qwen/qwen3.8-27b
    agent_model: str | None = None      # model the produced agent runs on (defaults to model)
    judge_model: str | None = None      # judge model; set a different family to reduce self preference
    judge_backend: str | None = None
    guard_model: str | None = None      # decides cross-document contradictions (defaults to the judge model)
    base_url: str | None = None
    api_key: str | None = None
    embedding: str = "wordllama"        # wordllama (offline, bundled) | fastembed:BAAI/bge-small-en-v1.5 | none

    # loop + budget
    max_iterations: int = 3
    min_gain: float = 0.02             # stop early if an iteration improves dev pass rate by less than this
    max_tokens: int = 600_000
    max_seconds: float = 3 * 3600

    # eval generation targets
    n_answerable: int = 10
    n_cross_doc: int = 4
    n_ambiguous: int = 4
    n_out_of_scope: int = 5
    n_tool: int = 3
    holdout_fraction: float = 0.3
    seed: int = 7

    # stretch features
    tournament: bool = True
    tournament_candidates: int = 3
    tournament_cases: int = 10          # dev subset size used to pick the winning prompt
    judge_selftest: bool = True
    human_checkpoint: bool = False      # requester approves/edits requirements before generation
    interactive: bool = True            # ask clarifying questions on the terminal
    answers_file: str | None = None     # pre recorded answers for unattended runs
    verbose: bool = True

    tools_enabled: list[str] = field(default_factory=lambda: ["csv_lookup", "calculator", "weather_forecast", "current_date"])

    @classmethod
    def load(cls, path: str | None = None, **overrides) -> "Config":
        cfg = cls()
        p = Path(path) if path else Path("forgeai.yaml")
        if p.exists():
            data = yaml.safe_load(p.read_text()) or {}
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        env_map = {
            "FORGE_BACKEND": "backend",
            "FORGE_MODEL": "model",
            "FORGE_AGENT_MODEL": "agent_model",
            "FORGE_JUDGE_MODEL": "judge_model",
            "FORGE_JUDGE_BACKEND": "judge_backend",
            "FORGE_GUARD_MODEL": "guard_model",
            "FORGE_BASE_URL": "base_url",
            "FORGE_EMBEDDING": "embedding",
        }
        for env, attr in env_map.items():
            if os.environ.get(env):
                setattr(cfg, attr, os.environ[env])
        for k, v in overrides.items():
            if v is not None and hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def public_dict(self) -> dict:
        d = asdict(self)
        d.pop("api_key", None)
        return d
