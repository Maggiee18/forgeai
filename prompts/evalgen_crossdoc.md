TASK: evalgen_crossdoc
Write ONE realistic question from a {{audience}} whose complete answer needs information from BOTH excerpts.
Each excerpt comes from a different document.

EXCERPT A (from {{source_a}}):
"""
{{chunk_a}}
"""

EXCERPT B (from {{source_b}}):
"""
{{chunk_b}}
"""

Rules:
- Do not mention documents or excerpts in the question.
- facts_a: 1 or 2 facts from excerpt A the answer must contain; facts_b: 1 or 2 facts from excerpt B.
  Copy numbers and names exactly. Each fact under 15 words. Facts must answer what is asked, not repeat it.
- If the two excerpts truly cannot be combined into one natural question, reply {"question": ""}.

Reply with JSON only:
{"question": "...", "facts_a": ["..."], "facts_b": ["..."]}
