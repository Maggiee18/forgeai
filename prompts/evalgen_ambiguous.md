TASK: evalgen_ambiguous
Rewrite each question the way a hurried real user would type it: informal, vague or indirect wording,
maybe a typo or abbreviation, maybe a different word for the key term. Keep the same meaning and the same
correct answer. Do not add new requirements.

QUESTIONS:
{{questions}}

Reply with JSON only:
{"rewrites": ["...", "..."]}  (same order, same count)
