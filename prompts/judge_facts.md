TASK: judge_facts
You grade an assistant's answer against required facts. Grade each fact independently.
A fact counts as stated only if the answer says it (same meaning; numbers must match exactly).
Length does not matter: a long answer gets no credit for extra text and a short answer loses nothing for brevity.
Ignore tone and formatting. If the answer contradicts a fact, it is not stated.

QUESTION: {{question}}

ANSWER:
"""
{{answer}}
"""

REQUIRED FACTS:
{{facts}}

Reply with JSON only:
{"verdicts": [{"fact": 1, "stated": true, "quote": "exact words from the ANSWER that state it, or empty"}]}
