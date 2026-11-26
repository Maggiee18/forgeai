TASK: optimizer_patch
You are fixing ONE section of an assistant's system prompt. Do not rewrite the assistant; make a targeted edit.

FAILURE CATEGORY: {{category}}
WHAT WENT WRONG (abstracted from failing test cases):
{{failures}}

CURRENT "{{section}}" SECTION:
"""
{{current}}
"""

Write the improved "{{section}}" section. Keep every existing rule that still applies, and add or sharpen at most
3 short rules that would prevent these failures in general. Do NOT quote the test questions or their answers;
write general rules. Keep it under 12 lines.

Reply with JSON only:
{"section_text": "...", "rationale": "one sentence on what the edit fixes"}
