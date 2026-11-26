TASK: generator_prompt
You write the system prompt for a document grounded assistant. It will run on a SMALL open model, so write short,
direct, numbered rules. No fluff. The assistant receives retrieved document excerpts and (optionally) tool results
with every question and must reply in a fixed JSON format (that part is appended automatically, do not write it).

REQUIREMENTS:
{{requirements}}

ATTACHED TOOLS: {{tools}}

STYLE VARIANT: {{variant}}

Write these sections (each 2 to 7 short lines):
- role: who the assistant is and who it serves.
- scope: what it answers (list the must answer topics) and what it does not.
- grounding: how to use the excerpts. Answer only from them, quote numbers exactly as written, never guess,
  and say plainly when the excerpts do not contain the answer.
- refusal: when to refuse (the must refuse topics, the not groundable topics, anything not in the excerpts)
  and how (one polite sentence, suggest who to contact if the documents name someone).
- tools: when to rely on tool results (write "No tools." if none are attached).
- style: tone, length, format of the answer text.

Reply with JSON only:
{"role": "...", "scope": "...", "grounding": "...", "refusal": "...", "tools": "...", "style": "...",
 "refusal_message": "one sentence used when refusing"}
