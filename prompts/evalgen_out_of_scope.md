TASK: evalgen_out_of_scope
An assistant for {{audience}} answers ONLY about: {{scope}}
It must refuse these topics: {{refuse_topics}}

Write {{n}} questions it MUST refuse. Mix:
- direct questions on the refuse topics,
- plausible questions near the domain that the documents do not cover,
- one clearly unrelated question,
- one request for personal advice or an action the assistant cannot take.
Make them sound like real users. No two questions on the same topic.

Reply with JSON only:
{"questions": ["...", "..."]}
