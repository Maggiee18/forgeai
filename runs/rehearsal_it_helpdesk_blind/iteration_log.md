# Critic → optimizer iteration log

## Iteration 1  (agent v0 → v1)
Dev pass rate before: **72%**, after: **72%** · holdout before 100%, after 100% · decision: **reverted (dev score did not improve)**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 4}
- **prompt_defect → prompt.style**: Ensures all key facts are captured and prevents truncation of important information.
  - addressed cases: ans-04, cro-01, cro-04, amb-03
  - actually fixed: none; newly broken anywhere: none
  - new section text:
    ```
    Friendly yet professional, concise, 2–4 sentences, mention conditions or exceptions. Answers are in plain text, no fluff. Always include every key fact from the retrieved passage. If multiple facts are present, list them in order of appearance. Do not truncate the answer; provide a complete response within the sentence limit.
    ```
- **wrong_refusal → prompt.refusal**: Adds explicit prohibition on providing policy documents or location-based answers, preventing under‑refusal of policy‑related queries.
  - addressed cases: out-04
  - actually fixed: none; newly broken anywhere: none
  - new section text:
    ```
    Refuse any request that requires detailed troubleshooting, HR/legal advice, personal data, non‑catalogue items, non‑eligible roles, or external vendor info. Do not provide policy documents, internal procedures, or location-based answers. Respond politely, suggest contacting the Service Desk if a name is provided, and do not offer any workaround or partial compliance. Do not offer to search for or summarize policy content. Do not provide any information that could be used to bypass security or privacy controls.
    ```

## Iteration 2  (agent v0 → v2)
Dev pass rate before: **72%**, after: **n/a** · holdout before 100%, after n/a · decision: **no change**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 4}
- **prompt_defect → -**: an earlier fix for this category was reverted; not retrying the same targeted fix
  - skipped: an earlier fix for this category was reverted; not retrying the same targeted fix
  - addressed cases: ans-04, cro-01, cro-04, amb-03
- **wrong_refusal → -**: an earlier fix for this category was reverted; not retrying the same targeted fix
  - skipped: an earlier fix for this category was reverted; not retrying the same targeted fix
  - addressed cases: out-04

Stopped: optimizer found no applicable targeted fix
