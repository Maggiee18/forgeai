TASK: agent_answer
EXCERPTS (numbered, with source file):
{{context}}

TOOL RESULTS:
{{tool_results}}

{{history}}QUESTION: {{question}}

Reply with JSON only, exactly this shape:
{"answer": "your answer to the user", "refused": false, "citations": ["file names of the excerpts you used"]}
If you must refuse or the excerpts do not contain the answer, set "refused": true, explain briefly in "answer",
and use "citations": [].
