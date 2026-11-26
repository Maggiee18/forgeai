"""Document loading and inspection. Supports PDF, CSV, TXT, MD and DOCX."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".pdf", ".csv", ".txt", ".md", ".docx"}


@dataclass
class Document:
    doc_id: str          # file name, used as the citation key
    path: str
    kind: str            # pdf | csv | text
    text: str
    pages: int = 1
    rows: list[dict] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_document(path: Path) -> Document | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [p.extract_text() or "" for p in reader.pages]
        return Document(path.name, str(path), "pdf", _clean("\n\n".join(pages)), pages=len(pages))
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0].keys()) if rows else []
        text = "\n".join("; ".join(f"{k}: {v}" for k, v in r.items()) for r in rows)
        return Document(path.name, str(path), "csv", text, rows=rows, columns=cols)
    if ext in {".txt", ".md"}:
        return Document(path.name, str(path), "text", _clean(path.read_text(encoding="utf-8", errors="ignore")))
    if ext == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            return None
        d = docx.Document(str(path))
        return Document(path.name, str(path), "text", _clean("\n".join(p.text for p in d.paragraphs)))
    return None


def load_folder(folder: str | Path) -> list[Document]:
    folder = Path(folder)
    docs = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            d = load_document(p)
            if d and (d.text.strip() or d.rows):
                docs.append(d)
    return docs


_HEADING = re.compile(r"^(\d+(\.\d+)*\.?\s+\S.{0,70}|[A-Z][A-Za-z/&,\- ]{2,60})$")


def headings(doc: Document, limit: int = 25) -> list[str]:
    out = []
    for line in doc.text.split("\n"):
        line = line.strip()
        if 3 <= len(line) <= 75 and _HEADING.match(line) and not line.endswith("."):
            out.append(line)
        if len(out) >= limit:
            break
    return out


def inventory(docs: list[Document]) -> list[dict]:
    """Compact description of the folder that fits in a small model's context."""
    inv = []
    for d in docs:
        item = {"doc": d.doc_id, "kind": d.kind, "words": len(d.text.split())}
        if d.kind == "csv":
            item["rows"] = len(d.rows)
            item["columns"] = d.columns
            item["sample_rows"] = d.rows[:3]
        else:
            item["pages"] = d.pages
            item["sections"] = headings(d)
            item["opening"] = " ".join(d.text.split()[:60])
        inv.append(item)
    return inv


def inventory_text(docs: list[Document], max_chars: int = 5000) -> str:
    lines = []
    for item in inventory(docs):
        if item["kind"] == "csv":
            lines.append(f"- {item['doc']} (CSV, {item['rows']} rows) columns: {', '.join(item['columns'])}")
            for r in item["sample_rows"][:2]:
                lines.append(f"    sample row: {r}")
        else:
            lines.append(f"- {item['doc']} ({item['kind']}, {item['pages']} pages, {item['words']} words)")
            if item["sections"]:
                lines.append(f"    sections: {' | '.join(item['sections'][:18])}")
            lines.append(f"    opens with: {item['opening']}")
    s = "\n".join(lines)
    return s[:max_chars]
