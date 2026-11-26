# Critic → optimizer iteration log

## Iteration 1  (agent v0 → v1)
Dev pass rate before: **89%**, after: **89%** · holdout before 100%, after 100% · decision: **reverted (dev score did not improve)**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 1}
- **wrong_refusal → prompt.refusal**: Adds explicit rule to refuse when freight quote details are missing, preventing over‑refusal of valid excerpted information.
  - addressed cases: amb-03
  - actually fixed: none; newly broken anywhere: none
  - new section text:
    ```
    Refuse personal advice, non‑procurement, legal, financial planning beyond scope, non‑maritime, supplier‑unrelated, or unverified external questions. For any request that requires a freight quote or other data not present in the provided excerpts, state that the information is not covered and set refused to true. If the user asks for a specific number of quotes or details not in the excerpts, refuse and suggest consulting the document author or designated contact. Do not provide any answer based on memory or external sources.
    ```

## Iteration 2  (agent v0 → v2)
Dev pass rate before: **89%**, after: **n/a** · holdout before 100%, after n/a · decision: **no change**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 1}
- **wrong_refusal → -**: an earlier fix for this category was reverted; not retrying the same targeted fix
  - skipped: an earlier fix for this category was reverted; not retrying the same targeted fix
  - addressed cases: amb-03

Stopped: optimizer found no applicable targeted fix
