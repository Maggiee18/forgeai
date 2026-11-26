"""Small, dependency free text helpers shared by retrieval, eval validation and the judge."""
from __future__ import annotations

import re

STOP = set(
    """a an the and or of to in on for at by with from as is are was were be been being this that these those it its
    i you he she we they me my your our their them his her what which who whom whose when where why how can could
    should would will shall may might must do does did done have has had not no yes if then than so such any all each
    per about into over under up down out more most less least very also just only there here please tell know
    much many get gets got one""".split()
)

_NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?:\s?[kK]\b|\s?(?:lakh|lakhs)\b)?")


def stem(w: str) -> str:
    for suf in ("ings", "ing", "ies", "ied", "edly", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            if suf in ("ies", "ied"):
                return w[: -len(suf)] + "y"
            return w[: -len(suf)]
    return w


def tokens(text: str, keep_stop: bool = False) -> list[str]:
    raw = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
    return [stem(t) for t in raw if keep_stop or t not in STOP]


_WORDNUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
_WORDNUM.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100})
_WORD_RE = re.compile(r"\b(" + "|".join(_WORDNUM) + r")\b", re.I)


def numbers(text: str) -> set[str]:
    """Numbers in a text, normalised: '1,500.00' -> '1500', 'two' -> '2'."""
    out = {str(_WORDNUM[w.lower()]) for w in _WORD_RE.findall(text or "") if w.lower() not in ("zero", "one")}
    for m in _NUM.findall(text or ""):
        mult = 1
        low = m.lower().strip()
        if low.endswith("k"):
            mult, m = 1000, m.strip()[:-1]
        elif low.endswith("lakh") or low.endswith("lakhs"):
            mult, m = 100000, re.sub(r"\s?lakhs?$", "", m.strip(), flags=re.I)
        v = m.replace(",", "").strip()
        try:
            f = float(v) * mult
        except ValueError:
            continue
        out.add(str(int(f)) if f == int(f) else str(round(f, 4)).rstrip("0").rstrip("."))
    return out


_LABEL = re.compile(r"\b(level|tier|grade|section|step|stage|phase|clause|part|item|g|annex|appendix|chapter|rule|no\.?)\s?(\d+)\b", re.I)


def value_numbers(fact: str, question: str = "") -> set[str]:
    """Numbers a correct answer must repeat: drops labels ("Level 2", "Tier 1", "G3") and numbers the
    question already states (the answer need not echo them)."""
    labels = numbers(" ".join(m.group(2) for m in _LABEL.finditer(fact)))
    return numbers(fact) - labels - numbers(question)


def content_overlap(fact: str, text: str) -> float:
    """Fraction of the fact's content tokens that appear in text."""
    ft = set(tokens(fact))
    if not ft:
        return 1.0
    tt = set(tokens(text))
    return len(ft & tt) / len(ft)


def jaccard(a: str, b: str) -> float:
    x, y = set(tokens(a)), set(tokens(b))
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def fact_in_text(fact: str, text: str, min_overlap: float = 0.6, question: str = "") -> bool:
    """Deterministic fact match: every value number in the fact must appear in the text,
    and most of its content words must too."""
    fn = value_numbers(fact, question) if question else numbers(fact)
    if fn and not fn <= numbers(text):
        return False
    return content_overlap(fact, text) >= (min_overlap if not fn else min(min_overlap, 0.5))


def quote_in_text(quote: str, text: str, min_overlap: float = 0.8) -> bool:
    if not quote or not quote.strip():
        return False
    q = " ".join(quote.lower().split())
    t = " ".join(text.lower().split())
    if q in t:
        return True
    return content_overlap(quote, text) >= min_overlap and numbers(quote) <= numbers(text)


REFUSAL_PATTERNS = re.compile(
    r"(i (?:do not|don't|cannot|can't|am unable to|am not able to) (?:find|answer|help|provide|see|have)|"
    r"not (?:covered|addressed|mentioned|included|available|specified|stated) in|"
    r"outside (?:of )?(?:my|the) (?:scope|documents)|beyond (?:my|the) scope|"
    r"no information (?:about|on|regarding)|documents? (?:do|does) not (?:cover|contain|mention|say|specify)|"
    r"unable to (?:answer|help|find))",
    re.I,
)


def looks_like_refusal(text: str) -> bool:
    return bool(REFUSAL_PATTERNS.search(text or ""))
