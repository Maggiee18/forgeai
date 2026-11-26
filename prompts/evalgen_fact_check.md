TASK: evalgen_fact_check
A test case checks whether an assistant's answer contains required facts. Decide, for each fact, whether a
complete and correct answer to EXACTLY this question must contain it.

A fact is NOT required when it:
- only repeats information already given in the question,
- answers a different question (a related rule, an exception, a case the question does not ask about),
- is background the user did not ask for.

QUESTION: {{question}}

FACTS:
{{facts}}

Reply with JSON only:
{"verdicts": [{"fact": 1, "required": true or false, "why": "a few words"}]}
