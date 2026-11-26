TASK: generator_tools
Pick the tools this assistant needs from the registry. Attach a tool ONLY if the requirements clearly need it.
An assistant that only answers questions from policy documents needs no tools at all. Every extra tool is a defect.

REQUIREMENTS:
{{requirements}}

DOCUMENTS INCLUDE CSV DATA: {{has_csv}}

TOOL REGISTRY:
{{registry}}

Reply with JSON only:
{"tools": [{"name": "tool_name", "reason": "which requirement needs it"}]}
(use {"tools": []} when none are needed)
