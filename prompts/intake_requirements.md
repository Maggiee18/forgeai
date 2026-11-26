TASK: intake_requirements
You turn a brief plus a clarification interview into a structured requirements document for an AI assistant
that will answer ONLY from the requester's documents.

BRIEF:
{{brief}}

DOCUMENT FOLDER:
{{inventory}}

CLARIFICATIONS (question -> answer):
{{clarifications}}

Rules:
- must_answer_topics: 4 to 10 concrete topics users will ask about, phrased as short noun phrases. Include
  every topic the brief or the answers ask for, even ones the documents may not cover (a later check flags those).
- must_refuse_topics: 3 to 8 topics the assistant must decline (out of scope, unsafe, personal advice, things
  for other departments, anything the requester excluded).
- tool_needs: list capabilities needed beyond reading documents, in plain words (for example "multiply price by
  quantity", "look up a part in the catalogue", "today's date for delivery dates", "weather at a port").
  Use an empty list if the assistant only needs to read documents.
- tone: one sentence. audience: who asks. scope: two sentences max.
- agent_name: short, lowercase, words joined by dashes.
- uncertainties: 0 to 4 things that are still unclear after the interview and could change the assistant's
  behaviour (for example "whether contractors are covered"). Empty list if nothing is unclear.

Reply with JSON only:
{"agent_name": "...", "purpose": "...", "scope": "...", "audience": "...", "tone": "...",
 "must_answer_topics": ["..."], "must_refuse_topics": ["..."], "tool_needs": ["..."], "uncertainties": ["..."]}
