TASK: guard_topic
You check whether a document collection can support answers about a topic. Be strict: "supported" only if the
excerpts contain specific information (rules, numbers, procedures) about the topic itself. A passing mention or a
related but different topic is "partial" or "unsupported". Never use outside knowledge.

TOPIC: {{topic}}

EXCERPTS (best matches from the documents):
{{excerpts}}

Reply with JSON only:
{"status": "supported|partial|unsupported",
 "evidence_quote": "copy the single most relevant sentence EXACTLY from the excerpts, or empty if unsupported",
 "source": "file name the quote comes from, or empty"}
