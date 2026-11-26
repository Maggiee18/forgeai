"""Tool registry the factory chooses from.

Each tool declares the *evidence* that justifies attaching it. The generator's
LLM proposes tools, then `select_tools` keeps only those whose evidence is
present in the requirements/documents. An HR agent with a weather tool is a
factory defect, so that check is deterministic and not left to the model.
"""
from __future__ import annotations

import ast
import csv
import datetime as dt
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests


@dataclass
class ToolSpec:
    name: str
    description: str
    args: dict            # arg name -> description
    need_keywords: list[str]  # words in brief/requirements that indicate the need
    needs_csv: bool = False
    output_schema: dict = field(default_factory=dict)
    func: Callable | None = field(default=None, repr=False)

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in self.args.items()}}

    def describe(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema(), "output_schema": self.output_schema}


# ----------------------------------------------------------------- calculator
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}
_FUNCS = {"round": round, "min": min, "max": max, "abs": abs, "sum": lambda *a: sum(a)}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calculator(expression: str, **_) -> dict:
    expr = str(expression).replace(",", "").replace("^", "**").replace("×", "*")
    expr = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", expr)
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr)
    try:
        val = _eval(ast.parse(expr, mode="eval"))
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not evaluate '{expression}': {e}"}
    if isinstance(val, float):
        val = round(val, 4)
    return {"expression": expression, "result": val}


# --------------------------------------------------------------- current date
def current_date(days_from_now: int | str = 0, **_) -> dict:
    try:
        n = int(float(days_from_now or 0))
    except ValueError:
        n = 0
    today = dt.date.today()
    target = today + dt.timedelta(days=n)
    return {"today": today.isoformat(), "weekday": today.strftime("%A"), "days_from_now": n, "date": target.isoformat(), "target_weekday": target.strftime("%A")}


# ------------------------------------------------------------- weather (HTTP)
def weather_forecast(location: str = "", latitude: float | None = None, longitude: float | None = None, **_) -> dict:
    """Keyless open-meteo API: geocode a place name, return current + 3 day forecast."""
    try:
        if latitude is None or longitude is None:
            g = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": location, "count": 1}, timeout=15).json()
            if not g.get("results"):
                return {"error": f"location '{location}' not found"}
            r0 = g["results"][0]
            latitude, longitude, location = r0["latitude"], r0["longitude"], f"{r0['name']}, {r0.get('country','')}"
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude, "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                "forecast_days": 3, "timezone": "auto",
            },
            timeout=15,
        ).json()
        return {"location": location, "current": w.get("current"), "daily": w.get("daily")}
    except Exception as e:  # noqa: BLE001
        return {"error": f"weather API unreachable: {e}"}


# ----------------------------------------------------------------- csv lookup
class CsvLookup:
    """Filter rows of the CSV files that ship with the agent's documents."""

    def __init__(self, csv_paths: list[str]):
        self.tables = {}
        for p in csv_paths:
            with open(p, newline="", encoding="utf-8-sig") as f:
                self.tables[Path(p).name] = list(csv.DictReader(f))

    def schema(self) -> str:
        return "; ".join(f"{n} columns=[{', '.join(rows[0].keys()) if rows else ''}]" for n, rows in self.tables.items())

    def __call__(self, column: str = "", value: str = "", file: str | None = None, limit: int = 5, **_) -> dict:
        tables = {file: self.tables[file]} if file in self.tables else self.tables
        value_l = str(value).lower().strip()
        hits = []
        for name, rows in tables.items():
            for r in rows:
                cols = [c for c in r if c.lower() == str(column).lower()] or list(r.keys())
                for c in cols:
                    cell = str(r.get(c, "")).lower()
                    if value_l and (value_l == cell or value_l in cell):
                        hits.append({"file": name, **r})
                        break
        if not hits and value_l:
            # token fallback: rows that contain every token of the value somewhere
            toks = [t for t in re.split(r"\W+", value_l) if t]
            for name, rows in tables.items():
                for r in rows:
                    blob = " ".join(str(v).lower() for v in r.values())
                    if toks and all(t in blob for t in toks):
                        hits.append({"file": name, **r})
        return {"matches": hits[: int(limit or 5)], "total_matches": len(hits)}


REGISTRY: dict[str, ToolSpec] = {
    "csv_lookup": ToolSpec(
        "csv_lookup",
        "Look up rows in the agent's CSV data files by column and value (exact or contains match).",
        {"column": "column name to search", "value": "value or substring to match", "file": "optional CSV file name"},
        need_keywords=["catalogue", "catalog", "part number", "stock", "price list", "inventory", "sku", "lookup", "table", "spares", "item code"],
        needs_csv=True,
        output_schema={"type": "object", "properties": {"matches": {"type": "array", "items": {"type": "object"}}, "total_matches": {"type": "integer"}}},
    ),
    "calculator": ToolSpec(
        "calculator",
        "Evaluate an arithmetic expression exactly, e.g. '12 * 450 * (1 - 0.05)'.",
        {"expression": "arithmetic expression using numbers, + - * / ( ) and %"},
        need_keywords=["total", "cost", "calculate", "compute", "quantity", "discount", "sum", "how much", "price", "budget", "estimate", "pro rata", "prorat", "multiply"],
        output_schema={"type": "object", "properties": {"expression": {"type": "string"}, "result": {"type": "number"}, "error": {"type": "string"}}},
    ),
    "weather_forecast": ToolSpec(
        "weather_forecast",
        "Current weather and 3 day forecast for a named place (open-meteo, keyless).",
        {"location": "city or port name"},
        need_keywords=["weather", "forecast", "wind", "rain", "storm", "temperature", "sea state", "monsoon"],
        output_schema={"type": "object", "properties": {"location": {"type": "string"}, "current": {"type": "object"}, "daily": {"type": "object"}, "error": {"type": "string"}}},
    ),
    "current_date": ToolSpec(
        "current_date",
        "Today's date and weekday; optionally the date N days from now (for deadlines, lead times).",
        {"days_from_now": "optional integer offset in days"},
        need_keywords=["today", "date", "deadline", "lead time", "delivery date", "when will", "days from now", "expiry", "due"],
        output_schema={"type": "object", "properties": {"today": {"type": "string", "format": "date"}, "weekday": {"type": "string"}, "days_from_now": {"type": "integer"}, "date": {"type": "string", "format": "date"}}},
    ),
}
REGISTRY["calculator"].func = calculator
REGISTRY["current_date"].func = current_date
REGISTRY["weather_forecast"].func = weather_forecast


def evidence_for(tool: str, requirement_text: str, has_csv: bool) -> list[str]:
    spec = REGISTRY[tool]
    if spec.needs_csv and not has_csv:
        return []
    t = requirement_text.lower()
    hits = [k for k in spec.need_keywords if re.search(r"\b" + re.escape(k), t)]
    if spec.needs_csv and has_csv:
        hits.append("documents include CSV data")
    return hits


def select_tools(proposed: list[dict], requirement_text: str, has_csv: bool, enabled: list[str]) -> tuple[list[dict], list[dict]]:
    """Intersect the LLM's proposal with deterministic evidence. Returns (kept, rejected)."""
    kept, rejected = [], []
    seen = set()
    for p in proposed:
        name = p.get("name") if isinstance(p, dict) else str(p)
        if name in seen:
            continue
        seen.add(name)
        if name not in REGISTRY or name not in enabled:
            rejected.append({"name": name, "reason": "not in the tool registry"})
            continue
        ev = evidence_for(name, requirement_text, has_csv)
        # csv_lookup needs both a CSV and a lookup style need; a CSV alone is enough evidence
        strong = [e for e in ev if e != "documents include CSV data"]
        if name == "csv_lookup":
            ok = has_csv
        elif name == "calculator":
            ok = len(strong) >= 2  # 'cost' alone in an HR brief is not enough
        else:
            ok = len(strong) >= 1
        if ok:
            kept.append({"name": name, "reason": (p.get("reason") if isinstance(p, dict) else "") or "", "evidence": ev})
        else:
            rejected.append({"name": name, "reason": f"model proposed it but requirements show no need (evidence found: {ev or 'none'})"})
    return kept, rejected


def make_tool_functions(tool_names: list[str], csv_paths: list[str]) -> dict[str, Callable]:
    fns = {}
    for n in tool_names:
        if n == "csv_lookup":
            if csv_paths:
                fns[n] = CsvLookup(csv_paths)
        elif n in REGISTRY and REGISTRY[n].func:
            fns[n] = REGISTRY[n].func
    return fns


def tool_menu(tool_names: list[str], csv_schema: str = "") -> str:
    lines = []
    for n in tool_names:
        s = REGISTRY[n]
        args = ", ".join(f"{k}: {v}" for k, v in s.args.items())
        extra = f" Data: {csv_schema}" if n == "csv_lookup" and csv_schema else ""
        lines.append(f"- {n}({args}): {s.description}{extra}")
    return "\n".join(lines)
