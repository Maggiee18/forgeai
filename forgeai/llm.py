"""LLM access layer.

One client, several interchangeable backends:
  * ollama   -> local model via http://localhost:11434 (fully offline)
  * groq     -> Groq's OpenAI compatible endpoint (small open models, free tier)
  * openai   -> any OpenAI compatible server (vLLM, LM Studio, llama.cpp server, ...)
  * mock     -> deterministic offline stand in used by the test suite

Every call goes through a shared Budget (token + wall clock accounting) and an
on disk cache, so a rerun of the same run is free and reproducible.
Small models break JSON often, so `json()` extracts, repairs and retries.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests


class BudgetExceeded(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass
class Budget:
    """Token / time budget shared by every LLM client in one factory run."""

    max_tokens: int = 600_000
    max_seconds: float = 3 * 3600
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cached_calls: int = 0
    started: float = field(default_factory=time.time)
    by_stage: dict = field(default_factory=dict)
    stage: str = "setup"

    def charge(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.tokens_used += prompt + completion
        self.calls += 1
        s = self.by_stage.setdefault(self.stage, {"tokens": 0, "calls": 0})
        s["tokens"] += prompt + completion
        s["calls"] += 1

    def remaining_tokens(self) -> int:
        return self.max_tokens - self.tokens_used

    def elapsed(self) -> float:
        return time.time() - self.started

    def check(self) -> None:
        if self.tokens_used >= self.max_tokens:
            raise BudgetExceeded(f"token budget exhausted ({self.tokens_used}/{self.max_tokens})")
        if self.elapsed() >= self.max_seconds:
            raise BudgetExceeded(f"time budget exhausted ({self.elapsed():.0f}s)")

    def to_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "tokens_used": self.tokens_used,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls": self.calls,
            "cached_calls": self.cached_calls,
            "elapsed_seconds": round(self.elapsed(), 1),
            "by_stage": self.by_stage,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model reply, repairing common breakage."""
    if text is None:
        raise ValueError("empty reply")
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    # drop <think>...</think> blocks emitted by some reasoning models
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    start = None
    for i, ch in enumerate(t):
        if ch in "{[":
            start = i
            break
    if start is None:
        raise ValueError("no JSON found")
    depth, in_str, esc = 0, False, False
    opener = t[start]
    closer = "}" if opener == "{" else "]"
    for j in range(start, len(t)):
        c = t[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                cand = t[start : j + 1]
                return json.loads(_repair(cand))
    # unterminated: try closing it
    return json.loads(_repair(t[start:] + closer))


def _repair(s: str) -> str:
    s = re.sub(r",\s*([}\]])", r"\1", s)  # trailing commas
    s = s.replace("“", '"').replace("”", '"')
    return s


class LLMClient:
    def __init__(
        self,
        backend: str,
        model: str,
        budget: Budget | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
        temperature: float = 0.2,
        mock_fn: Callable[[list[dict], bool], str] | None = None,
        role: str = "factory",
        verbose: bool = False,
    ):
        self.backend = backend
        self.model = model
        self.budget = budget or Budget()
        self.temperature = temperature
        self.role = role
        self.verbose = verbose
        self.mock_fn = mock_fn
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        if backend == "groq":
            self.base_url = base_url or "https://api.groq.com/openai/v1"
            self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        elif backend == "openai":
            self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        elif backend == "ollama":
            self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            self.api_key = ""
        elif backend == "mock":
            self.base_url, self.api_key = "", ""
        else:
            raise ValueError(f"unknown backend {backend}")

    # ------------------------------------------------------------------ public
    def describe(self) -> dict:
        return {"backend": self.backend, "model": self.model, "role": self.role}

    def chat(
        self,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int = 700,
    ) -> str:
        temp = self.temperature if temperature is None else temperature
        key = self._cache_key(messages, json_mode, temp, max_tokens)
        cached = self._cache_get(key)
        if cached is not None:
            self.budget.cached_calls += 1
            return cached
        self.budget.check()
        t0 = time.time()
        if self.backend == "mock":
            out = self.mock_fn(messages, json_mode) if self.mock_fn else "{}"
            p = sum(_estimate_tokens(m["content"]) for m in messages)
            self.budget.charge(p, _estimate_tokens(out))
        elif self.backend == "ollama":
            out = self._ollama(messages, json_mode, temp, max_tokens)
        else:
            out = self._openai_compat(messages, json_mode, temp, max_tokens)
        if self.verbose:
            print(f"    [llm:{self.role}] {time.time()-t0:.1f}s")
        self._cache_put(key, out)
        return out

    def json(
        self,
        messages: list[dict],
        validator: Callable[[Any], Any] | None = None,
        retries: int = 2,
        temperature: float | None = None,
        max_tokens: int = 900,
    ) -> Any:
        """Ask for JSON; on parse/validation failure, show the model its error and retry."""
        msgs = list(messages)
        last_err = None
        for attempt in range(retries + 1):
            raw = self.chat(msgs, json_mode=True, temperature=temperature if attempt == 0 else 0.0, max_tokens=max_tokens)
            try:
                data = extract_json(raw)
                if validator:
                    data = validator(data)
                return data
            except Exception as e:  # noqa: BLE001
                last_err = e
                msgs = list(messages) + [
                    {"role": "assistant", "content": raw[:1500]},
                    {
                        "role": "user",
                        "content": f"That reply was not valid for the required JSON format ({str(e)[:200]}). "
                        "Reply again with ONLY the corrected JSON object, nothing else.",
                    },
                ]
        raise LLMError(f"model failed to produce valid JSON after {retries+1} attempts: {last_err}")

    # ---------------------------------------------------------------- backends
    def _openai_compat(self, messages, json_mode, temp, max_tokens) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        body = {"model": self.model, "messages": messages, "temperature": temp, "max_tokens": max_tokens}
        if "gpt-oss" in self.model:
            # reasoning models spend hidden tokens before answering: keep effort low and leave room for it
            body["reasoning_effort"] = os.environ.get("FORGE_REASONING_EFFORT", "low")
            body["max_tokens"] = max_tokens + 1200
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last = ""
        for attempt in range(10):
            try:
                r = requests.post(url, json=body, headers=headers, timeout=120)
            except requests.RequestException as e:
                time.sleep(min(30, 2 ** attempt))
                last = str(e)
                continue
            if r.status_code == 429 and "per day" in r.text and (_retry_after(r) or 0) > 60:
                # daily quota on a rolling window: waiting is the only correct move. Wait what the provider asks
                # (capped at 30 min per wait), say so in the run log, and do not count it as a failed attempt.
                asked = min(1800.0, _retry_after(r) or 600)
                print(f"    [llm:{self.role}] daily token quota for {self.model} reached; waiting {asked/60:.1f} min for the rolling window to free up", flush=True)
                time.sleep(asked)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                asked = _retry_after(r)
                # never sleep blindly for long: cap each wait and keep retrying, and always say so in the run log
                wait = min(60.0, asked or (2 ** attempt + 1))
                print(f"    [llm:{self.role}] HTTP {r.status_code} from {self.backend}, waiting {wait:.0f}s"
                      + (f" (provider asked for {asked:.0f}s)" if asked and asked > wait else "") + f" · attempt {attempt + 1}/10", flush=True)
                time.sleep(wait)
                last = r.text[:300]
                continue
            if r.status_code == 400 and json_mode and "json" in r.text.lower():
                # model could not satisfy json_mode; fall back to plain mode and parse ourselves
                body.pop("response_format", None)
                json_mode = False
                last = r.text[:300]
                continue
            if r.status_code != 200:
                raise LLMError(f"{self.backend} HTTP {r.status_code}: {r.text[:400]}")
            data = r.json()
            usage = data.get("usage") or {}
            out = data["choices"][0]["message"].get("content") or ""
            if not out.strip() and data["choices"][0].get("finish_reason") == "length":
                body["max_tokens"] = int(body["max_tokens"] * 2)
                last = "empty reply (token limit hit during reasoning)"
                continue
            self.budget.charge(
                usage.get("prompt_tokens", sum(_estimate_tokens(m["content"]) for m in messages)),
                usage.get("completion_tokens", _estimate_tokens(out)),
            )
            return out
        raise LLMError(f"{self.backend} kept failing: {last}")

    def _ollama(self, messages, json_mode, temp, max_tokens) -> str:
        url = self.base_url.rstrip("/") + "/api/chat"
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temp, "num_predict": max_tokens, "num_ctx": 8192},
        }
        if json_mode:
            body["format"] = "json"
        r = requests.post(url, json=body, timeout=600)
        if r.status_code != 200:
            raise LLMError(f"ollama HTTP {r.status_code}: {r.text[:400]}")
        data = r.json()
        out = data.get("message", {}).get("content", "")
        self.budget.charge(data.get("prompt_eval_count", 0) or 0, data.get("eval_count", 0) or 0)
        return out

    # ------------------------------------------------------------------- cache
    def _cache_key(self, messages, json_mode, temp, max_tokens) -> str:
        blob = json.dumps(
            {"m": self.model, "b": self.backend, "msgs": messages, "j": json_mode, "t": temp, "x": max_tokens},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _cache_get(self, key):
        if not self.cache_dir:
            return None
        p = self.cache_dir / f"{key}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))["out"]
            except Exception:
                return None
        return None

    def _cache_put(self, key, out):
        if not self.cache_dir:
            return
        (self.cache_dir / f"{key}.json").write_text(json.dumps({"out": out}), encoding="utf-8")


def _retry_after(r) -> float | None:
    h = r.headers.get("retry-after")
    if h:
        try:
            return float(h) + 0.5
        except ValueError:
            pass
    m = re.search(r"try again in ([\d.]+)(ms|s)", r.text)
    if m:
        v = float(m.group(1))
        return (v / 1000 if m.group(2) == "ms" else v) + 0.5
    return None


def make_clients(cfg, budget: Budget, cache_dir: Path | None, mock_fn=None, verbose=False):
    """Build (factory, agent, judge) clients from a Config. The judge may use a
    different model to reduce self preference bias."""
    common = dict(budget=budget, cache_dir=cache_dir, mock_fn=mock_fn, verbose=verbose, base_url=cfg.base_url, api_key=cfg.api_key)
    factory = LLMClient(cfg.backend, cfg.model, temperature=0.2, role="factory", **common)
    agent = LLMClient(cfg.backend, cfg.agent_model or cfg.model, temperature=0.0, role="agent", **common)
    judge = LLMClient(cfg.judge_backend or cfg.backend, cfg.judge_model or cfg.model, temperature=0.0, role="judge", **common)
    return factory, agent, judge
