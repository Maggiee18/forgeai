# Critic → optimizer iteration log

## Iteration 1  (agent v0 → v1)
Dev pass rate before: **94%**, after: **100%** · holdout before 75%, after 88% · decision: **kept**

Failures going in, dev and holdout together (only dev failures reach the optimizer): {'retrieval_miss': 0, 'hallucination': 0, 'wrong_refusal': 1, 'prompt_defect': 2}
- **prompt_defect → prompt.style**: Adds rules to include all key facts, avoid truncation, and handle ambiguity, preventing missing information like 'escalate in writing'.
  - addressed cases: amb-03
  - actually fixed: amb-03; newly broken anywhere: none
  - new section text:
    ```
    Friendly, plain English, short sentences, quoted policy references, concise JSON output.
    - Ensure all key facts from the source are included in the answer.
    - Do not truncate policy excerpts; provide full relevant clauses.
    - If the question is ambiguous, list all applicable policy points and explain the reasoning.
    - Use bullet points for clarity when multiple facts are required.
    - Keep the answer within 2-3 sentences unless more detail is essential.
    - Verify that the answer directly addresses every part of the question.
    - Avoid assumptions; state any uncertainties explicitly.
    - Provide a brief summary of the policy context before the specific answer.
    - Use consistent terminology as defined in the policy.
    - Cite the policy section number or title in parentheses.
    - End with a concise conclusion or next step if applicable.
    ```
