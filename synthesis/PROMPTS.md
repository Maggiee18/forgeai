# Document synthesis prompts

Both demo document sets are LLM-synthesised for a fictional company, **Meridian Shipmanagement Pvt Ltd**
(Visakhapatnam / Mumbai). No real company policy is reproduced. The prompts below were used to produce the
source texts in `synthesis/source/`, which `synthesis/build_docs.py` renders into the PDFs and CSV that the
factory actually reads (`demos/*/docs/`). Numbers were then checked by hand for internal consistency
(for example, that leave accrual × 12 equals the annual entitlement).

## Shared system prompt

> You write realistic internal policy documents for a mid-sized Indian ship management company,
> Meridian Shipmanagement Pvt Ltd. Write like an HR or procurement department would: numbered sections,
> concrete numbers, conditions and exceptions, named roles (not named people), and a few cross references
> between documents. Use INR for money in HR documents and USD for marine spares. Avoid lorem-ipsum
> vagueness: every section must contain at least one specific rule, limit, timeline or procedure step.
> Do not include anything about salaries, pay bands or payroll dates.

The last line is deliberate: the HR brief asks for salary bands and payroll dates, so the factory's
groundability guard must flag that gap instead of letting the agent invent numbers.

## Demo 1: HR policy assistant (shore staff)

1. **Leave policy**
   > Write "Leave Policy: Shore Staff" (about 900 words). Cover: eligibility and leave year (Jan to Dec),
   > annual leave entitlement and monthly accrual, carry forward cap and encashment, sick leave with
   > certificate rule, casual leave, maternity, paternity, bereavement, marriage leave, public holidays,
   > applying through the HRMS portal with notice periods, leave without pay, leave during notice period,
   > and who approves. Mention that travel on leave is not reimbursable (see Travel and Expense Policy).

2. **Travel and expense policy**
   > Write "Travel and Expense Policy: Shore Staff" (about 900 words). Cover: grades (G1 to G5) and travel
   > class entitlement by air and rail, hotel caps by city tier in INR per night, daily allowance, local
   > conveyance and own vehicle mileage rate, travel advance limits and settlement, claim submission deadline
   > and late claims, receipts rule, non reimbursable items, international travel and visa, and approvals.
   > Cross reference the leave policy for travel combined with leave.

3. **Code of conduct and grievance procedure**
   > Write "Code of Conduct and Grievance Procedure" (about 900 words). Cover: working hours and hybrid
   > work days, attendance and late marks, dress code including vessel visits and PPE, gifts and hospitality
   > limit in INR, conflicts of interest declaration, confidentiality and social media, harassment (POSH
   > Internal Committee and complaint timeline), grievance escalation levels with response times in working
   > days, disciplinary process, and whistleblowing channel.

   **Deliberate contradiction (for the groundability guard):** after generation, one section was added to the
   travel policy saying gifts received on official trips may be kept up to INR 5,000, while the code of conduct
   caps gifts at INR 2,000. Real policy sets drift like this; the guard must detect it and the agent must give
   both rules with their sources instead of silently picking one.

**Regression variant (`demos/hr_policy/docs_v2`)**
   > Revise the leave policy as the 2027 edition: raise annual leave from 21 to 24 days (accrual 2 days a
   > month), raise the carry forward cap from 10 to 15 days, and raise paternity leave from 5 to 10 days.
   > Leave every other section unchanged.

## Demo 2: Ship spares procurement assistant

1. **Spares catalogue (CSV)**
   > Produce a CSV of 40 marine spare parts for a fleet of bulk carriers. Columns: part_number, description,
   > equipment, maker, unit, unit_price_usd, stock_on_hand, lead_time_days, min_order_qty, supplier.
   > Equipment spans main engine, auxiliary engines, purifiers, pumps, compressors, boilers, steering gear,
   > deck machinery and safety equipment. Suppliers are either Poseidon Marine Supplies or Harbourline Spares.
   > Prices realistic in USD; lead times 2 to 70 days; some parts with zero stock.

2. **Supplier terms: Poseidon Marine Supplies** and 3. **Supplier terms: Harbourline Spares**
   > Write the commercial terms sheet of a marine spares supplier (about 500 words): payment terms, volume
   > discount tiers on order value, urgent / AOG surcharge, delivery Incoterms and free delivery threshold,
   > documentation (certificates), warranty, returns and restocking fee, quotation validity. Make the two
   > suppliers differ on every number.

4. **Procurement procedure**
   > Write "Spares Procurement Procedure" (about 800 words) for the technical department: requisition
   > raising in the planned maintenance system, approval limits by order value (Chief Engineer,
   > Technical Superintendent, Fleet Manager, Technical Director), number of quotations required, OEM vs
   > non OEM rules, critical spares that must never be below minimum on board, urgent requisitions,
   > delivery to vessel and receipt confirmation, and documentation retention.
