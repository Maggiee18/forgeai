TASK: optimizer_expansion
A keyword search engine failed to find the right passage for user questions because users and documents use
different words. For each question, compare it with the passage that holds the answer and list word mappings:
a word or short phrase the USER used -> words the DOCUMENT uses for the same thing.

{{pairs}}

Rules: only map genuinely different wording (synonyms, abbreviations, informal terms). Document words must appear
in the passage. At most 3 mappings per question.
Reply with JSON only:
{"mappings": [{"user_term": "...", "document_terms": ["...", "..."]}]}
