TASK: agent_tool_plan
Decide whether tools are needed to answer the user's question, using the excerpts already retrieved.
Available tools:
{{tools}}

EXCERPTS:
{{context}}

QUESTION: {{question}}

Rules: call a tool only if the answer needs exact data lookup, arithmetic, a date, or live data that the excerpts
do not already give. At most 2 calls. If EARLIER TOOL RESULTS already contain what is needed, reply {"calls": []}.
Never repeat a call that is already in EARLIER TOOL RESULTS. For calculator, write a plain arithmetic expression using numbers from the
excerpts or earlier lookups.
Reply with JSON only:
{"calls": [{"tool": "name", "args": {"arg": "value"}}]}   or   {"calls": []}
