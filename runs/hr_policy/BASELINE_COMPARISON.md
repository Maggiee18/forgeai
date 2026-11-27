# Human baseline vs factory agent: `hr-policy-assistant`

Both agents answer the same generated test cases, with the same agent model, judge and retrieval engine. The human baseline
(`baseline/hr_human_agent.json`) was written by hand in about 25 minutes, without seeing the eval set.

| Metric | Factory agent (v1) | Human baseline |
|---|---|---|
| Overall pass rate | 96% | 88% |
| Dev | 100% | 88% |
| Holdout | 88% | 88% |
| Fact recall | 100% | 88% |
| Refusal accuracy | 86% | 100% |
| Grounded | 100% | 100% |
| Citation precision | 94% | 100% |
| Retrieval hit | 100% | 100% |

Cases only the factory agent passes: ans-10, cro-01, cro-02
Cases only the human baseline passes: out-03

- `ans-10` (factory passes): If I receive a gift worth INR 2,500 from a supplier, what must I do within 5 working days?  
  the other agent failed with **prompt_defect**: right passage retrieved but answer missed key facts ['Any gift of INR 2,000 or more must be declared to the Compliance Officer within']
- `cro-01` (factory passes): What steps should an employee take if they receive a gift worth INR 3,000 from a client during an official trip?  
  the other agent failed with **prompt_defect**: right passage retrieved but answer missed key facts ['Any gift of INR 2,000 or more must be declared to the Compliance Officer within']
- `cro-02` (factory passes): If I take up to 30 days of leave without pay after exhausting all paid leave, how does the 30‑day claim window for travel expenses affect my reimbursement process?  
  the other agent failed with **prompt_defect**: right passage retrieved but answer missed key facts ['Leave without pay of up to 30 days may be granted after all paid leave']
- `out-03` (human passes): Do I need to submit a legal affidavit for my leave?  
  the other agent failed with **wrong_refusal**: should have refused (out of scope or not covered) but answered
