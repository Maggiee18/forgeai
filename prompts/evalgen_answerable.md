TASK: evalgen_answerable
You write ONE test question for an AI assistant, using ONLY the excerpt below. A real user ({{audience}})
should plausibly ask it. The answer must be fully contained in the excerpt.

EXCERPT (from {{source}}):
"""
{{chunk}}
"""

Rules:
- The question must not mention "the document", "the excerpt" or the file name.
- key_facts: 1 to 3 short facts that a correct answer MUST contain. Copy numbers, durations, amounts and names
  EXACTLY as written in the excerpt. Each fact under 15 words.
- A key fact must be part of the ANSWER to exactly what is asked. Never include a fact that only repeats the
  question, and never include rules about cases the question does not ask about.
- Prefer questions whose answer is a specific rule, number, limit, procedure step or condition.

Reply with JSON only:
{"question": "...", "key_facts": ["...", "..."]}
