# Regression report: hr-policy-assistant v1

The documents changed. The original 25 test cases were re-run against two agents on the new documents:

- **Regenerated agent**: the factory rebuilt the agent from the same requirements on the new documents (prompt style `strict`, the original tournament winner). This is what a rebuild would ship.
- **Replayed agent**: the shipped definition unchanged (same prompt, tools and retrieval settings). This isolates the effect of the document change alone.

| Agent | Pass rate on the old eval set |
|---|---|
| Shipped agent, old documents | 96% |
| Regenerated agent, new documents | 88% |
| Replayed agent, new documents | 96% |

Tools: none before, none after regeneration.

## What changed in the documents (6 sentence level changes)

| Document | Change | Before | After | Covered by existing tests |
|---|---|---|---|---|
| Leave_Policy_Shore_Staff.pdf | changed | Leave Policy: Shore Staff Meridian Shipmanagement Pvt Ltd | Document HR-POL-03 | Edition 2026 1. | Leave Policy: Shore Staff Meridian Shipmanagement Pvt Ltd | Document HR-POL-03 | Edition 2027 1. | **none** |
| Leave_Policy_Shore_Staff.pdf | changed | Annual Leave Every confirmed employee is entitled to 21 days of annual leave per leave year. | Annual Leave Every confirmed employee is entitled to 24 days of annual leave per leave year. | **none** |
| Leave_Policy_Shore_Staff.pdf | changed | Annual leave accrues at 1.75 days for each completed month of service. | Annual leave accrues at 2 days for each completed month of service. | **none** |
| Leave_Policy_Shore_Staff.pdf | changed | Carry Forward and Encashment Unused annual leave of up to 10 days may be carried forward into the next leave y | Carry Forward and Encashment Unused annual leave of up to 15 days may be carried forward into the next leave y | **none** |
| Leave_Policy_Shore_Staff.pdf | changed | Any balance above 10 days lapses on 31 December. | Any balance above 15 days lapses on 31 December. | **none** |
| Leave_Policy_Shore_Staff.pdf | changed | Paternity Leave Male employees are entitled to 5 working days of paid paternity leave, to be taken within 3 mo | Paternity Leave Male employees are entitled to 10 working days of paid paternity leave, to be taken within 3 m | **none** |

## What broke: regenerated agent

| Case | Question | Failure | Verdict | Facts gone from the documents |
|---|---|---|---|---|
| ans-10 | If I receive a gift worth INR 2,500 from a supplier, what must I do within 5 wor | prompt_defect | agent regression: lost the fix the critic loop made in iteration 1 | - |
| amb-03 | If a grievance isn't solved by the reporting manager, how many working days does | prompt_defect | agent regression: lost the fix the critic loop made in iteration 1 | - |

Newly passing: none

**Why the regenerated agent scores lower:** ans-10, amb-03 only passed in the old run because the critic loop patched the prompt for them. Regeneration starts again from v0, so those learned fixes are lost. A real rebuild should run the full `forgeai build` (critic loop included) on the new documents, or carry the kept patches across.

## What broke: replayed agent

| Case | Question | Failure | Verdict | Facts gone from the documents |
|---|---|---|---|---|
| - | none | - | - | - |

Newly passing: none

## ⚠ 6 change(s) no existing test covers

A passing re-run says nothing about these. Rebuild the eval set (`forgeai build` on the new documents) so the changed rules are tested:

- Leave_Policy_Shore_Staff.pdf: "Leave Policy: Shore Staff Meridian Shipmanagement Pvt Ltd | Document HR-POL-03 | Edition 2027 1."
- Leave_Policy_Shore_Staff.pdf: "Annual Leave Every confirmed employee is entitled to 24 days of annual leave per leave year."
- Leave_Policy_Shore_Staff.pdf: "Annual leave accrues at 2 days for each completed month of service."
- Leave_Policy_Shore_Staff.pdf: "Carry Forward and Encashment Unused annual leave of up to 15 days may be carried forward into the next leave year."
- Leave_Policy_Shore_Staff.pdf: "Any balance above 15 days lapses on 31 December."
- Leave_Policy_Shore_Staff.pdf: "Paternity Leave Male employees are entitled to 10 working days of paid paternity leave, to be taken within 3 months of the birth or adoption"

## Guard flags on the new documents
- 'allowances' is only partly covered by the documents; answers may be incomplete.
- 'salary band' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- 'payroll dates' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- Conflicting information on Maximum value of retainable gifts from clients/agents: Code_of_Conduct_and_Grievance.pdf says "Employees may accept gifts or hospitality from suppliers, agents or clients only if the value is below INR 2,000 per occasion." while Travel_and_Expense_Policy.pdf says "Gifts received from clients or agents during an official trip may be retained if their value does not exceed INR 5,000.". The agent will present both and suggest confirming with the document owner.

Stale tests should be regenerated; agent regressions are real defects.