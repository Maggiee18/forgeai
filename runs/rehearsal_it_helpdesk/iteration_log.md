# Critic → optimizer iteration log

## Iteration 1  (agent v0 → v1)
Dev pass rate before: **86%**, after: **81%** · holdout before 100%, after 100% · decision: **reverted (dev score did not improve)**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 2}
- **prompt_defect → prompt.style**: Adds explicit rule to include all key facts and avoid truncation, addressing missed facts like "pre approved".
  - addressed cases: ans-04, amb-03
  - actually fixed: none; newly broken anywhere: cro-02
  - new section text:
    ```
    Friendly yet professional, concise, practical. Provide 2‑4 sentence explanations, mention conditions or exceptions. Ensure all key facts from the passage are included; if a fact is marked as "pre‑approved" or similar, explicitly state it. Avoid truncation—use full sentences or a brief list if necessary. Format responses in the required JSON structure.
    ```
- **wrong_refusal → prompt.refusal**: Adds explicit refusal for future events, missing policies, and personal data to prevent over‑refusal of valid questions.
  - addressed cases: amb-02
  - actually fixed: none; newly broken anywhere: cro-02
  - new section text:
    ```
    Refuse on any non‑IT HR, legal, personal data, live ticket or outage queries, or when the topic is not covered in the documents. Respond politely and suggest contacting the Service Desk if a name is provided.
    The documents do NOT cover the following, so never answer them from memory; say they are not covered and set refused to true: ticket status; system outage.
    Always refuse: detailed troubleshooting; non‑IT HR queries; legal advice; personal data requests; live ticket updates; live outage monitoring; external vendor support.
    Additions:
    - If the question asks for a future event or schedule that is not explicitly stated in the excerpts, refuse.
    - If the user requests a specific policy or procedure not present in the documents, refuse.
    - If the user asks for personal or sensitive information about an employee, refuse.
    ```

## Iteration 2  (agent v0 → v2)
Dev pass rate before: **86%**, after: **n/a** · holdout before 100%, after n/a · decision: **no change**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 2}
- **prompt_defect → -**: an earlier fix for this category was reverted; not retrying the same targeted fix
  - skipped: an earlier fix for this category was reverted; not retrying the same targeted fix
  - addressed cases: ans-04, amb-03
- **wrong_refusal → -**: an earlier fix for this category was reverted; not retrying the same targeted fix
  - skipped: an earlier fix for this category was reverted; not retrying the same targeted fix
  - addressed cases: amb-02

Stopped: optimizer found no applicable targeted fix
