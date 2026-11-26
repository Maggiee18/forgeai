# Requirements: hr-policy-assistant

**Purpose:** Provide concise, policy‑based answers to shore staff HR questions
**Scope:** Answers are drawn exclusively from the supplied policy documents and include salary band and payroll dates where available.
**Audience:** All shore‑based employees (grades G1‑G5) at Visakhapatnam and Mumbai offices
**Tone:** Friendly, plain English with short, quoted policy references

## Must answer
- leave balances
- leave entitlements
- working hours
- attendance
- dress code
- travel claims
- allowances
- grievance procedure
- salary band
- payroll dates

## Must refuse
- personal leave balances
- individual payroll queries
- legal advice
- seafarer policies
- confidential HRMS data
- salary negotiations
- non‑policy HR requests

## Tool needs
- none (documents only)

## Knowledge sources

| Document | Type | Size | Covers |
|---|---|---|---|
| Code_of_Conduct_and_Grievance.pdf | pdf | 2 pages, 552 words | Working Hours, Attendance, Dress Code, Gifts and Hospitality, Conflicts of Interest, Confidentiality and Social Media, Prevention of Sexual Harassment, Grievanc |
| Leave_Policy_Shore_Staff.pdf | pdf | 2 pages, 715 words | Leave Year, Annual Leave, Carry Forward and Encashment, Sick Leave, Casual Leave, Maternity Leave, Paternity Leave, Bereavement and Marriage Leave, Public Holid |
| Travel_and_Expense_Policy.pdf | pdf | 2 pages, 660 words | Employee Grades, Travel Class Entitlement, Hotel Accommodation, Daily Allowance, Local Conveyance, Travel Advance, Expense Claims, Gifts Received on Official Tr |

## Groundability check

| Topic | Status | Evidence | Source |
|---|---|---|---|
| leave balances | **supported** | Unused annual leave of up to 10 days may be carried forward into the next leave year. Any balance above 10 days lapses on 31 December. | Leave_Policy_Shore_Staff.pdf |
| leave entitlements | **supported** | Employees receive 6 days of casual leave per leave year. | Leave_Policy_Shore_Staff.pdf |
| working hours | **supported** | Office hours are 9:30 am to 6:00 pm, Monday to Friday, with a 45 minute lunch break. | Code_of_Conduct_and_Grievance.pdf |
| attendance | **supported** | Attendance is recorded through the biometric system. Arriving after 10:00 am is recorded as a late mark. Three late marks in a calendar mont | Code_of_Conduct_and_Grievance.pdf |
| dress code | **supported** | Business casual dress is expected in the office. Employees visiting a vessel, shipyard or terminal must wear safety shoes, a helmet and a hi | Code_of_Conduct_and_Grievance.pdf |
| travel claims | **supported** | Expense claims must be submitted in the HRMS portal within 30 days of completing the trip. | Travel_and_Expense_Policy.pdf |
| allowances | **partial** | A daily allowance covers meals and incidental expenses. It is INR 1,200 per day for G1 and G2 and INR 1,800 per day for G3 and above. | Travel_and_Expense_Policy.pdf |
| grievance procedure | **supported** | Employees with a work related grievance should follow these levels in order. Level 1: raise the grievance with the reporting manager, who mu | Code_of_Conduct_and_Grievance.pdf |
| salary band | **unsupported** |  |  |
| payroll dates | **unsupported** |  |  |

## Conflicting information across documents

- **Maximum value of retainable gifts from clients/agents**
  - Code_of_Conduct_and_Grievance.pdf: "Employees may accept gifts or hospitality from suppliers, agents or clients only if the value is below INR 2,000 per occasion."
  - Travel_and_Expense_Policy.pdf: "Gifts received from clients or agents during an official trip may be retained if their value does not exceed INR 5,000."
  - why it is the same subject: Both passages define the threshold for retaining gifts from clients or agents, but they provide different monetary limits (INR 2,000 vs INR 5,000) without Passage A explicitly acknowledging the travel exception found in Passage B. (second model openai/gpt-oss-20b disagreed)

## Flags raised at requirements stage
- ⚠ 'allowances' is only partly covered by the documents; answers may be incomplete.
- ⚠ 'salary band' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- ⚠ 'payroll dates' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- ⚠ Conflicting information on Maximum value of retainable gifts from clients/agents: Code_of_Conduct_and_Grievance.pdf says "Employees may accept gifts or hospitality from suppliers, agents or clients only if the value is below INR 2,000 per occasion." while Travel_and_Expense_Policy.pdf says "Gifts received from clients or agents during an official trip may be retained if their value does not exceed INR 5,000.". The agent will present both and suggest confirming with the document owner.

## Recommended clarifications or scope changes
- Either add a source document covering 'salary band' or remove it from the scope.
- Either add a source document covering 'payroll dates' or remove it from the scope.
- Ask the document owners which rule on Maximum value of retainable gifts from clients/agents is current, and fix the outdated document.

## Known limitations
- Partial coverage: allowances.
- Cannot answer: salary band (not in the documents).
- Cannot answer: payroll dates (not in the documents).
- Documents contradict each other on Maximum value of retainable gifts from clients/agents; answers cite both versions.
- Answers only from the supplied documents; no access to personal records or live systems.

## Uncertainties and assumptions
- Assumed (nobody answered): Should the assistant perform any calculations (e.g., leave balance, carry‑forward limits) or just provide static policy text? -> Only provide static policy text; no calculations.

## Clarifying interview

1. **Who are the primary users of the assistant (e.g., all shore staff, specific departments, or only HR personnel)?**  
   _answers_file_: All shore based employees in Visakhapatnam and Mumbai, grades G1 to G5. Not seafarers; their leave is under the CBA.
2. **What tone should the assistant adopt when responding (e.g., formal, conversational, or a mix)?**  
   _answers_file_: Friendly, plain English, short answers that quote the exact number or limit from the policy.
3. **Are there any topics explicitly out of scope that the assistant should refuse to answer (e.g., personal salary details beyond band, or legal advice)?**  
   _answers_file_: No personal balances or individual cases; it cannot see HRMS data. It explains the rules only.
4. **How should the assistant handle questions about payroll dates and salary bands that may not be fully detailed in the documents?**  
   _answers_file_: Yes, staff want salary bands and payroll dates included if possible.
5. **Should the assistant perform any calculations (e.g., leave balance, carry‑forward limits) or just provide static policy text?**  
   _assumed_: Only provide static policy text; no calculations.

**Approved:** True (human checkpoint disabled (unattended run))