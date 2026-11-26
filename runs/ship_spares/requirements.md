# Requirements: spareproc-assistant

**Purpose:** Provide procurement assistance for ship superintendents and purchasing staff by sourcing spare parts, calculating costs, estimating delivery, and quoting freight.
**Scope:** Answers only from the supplied documents, including catalogue, procurement procedure, and supplier terms. No external data beyond live freight rates.
**Audience:** Technical superintendents, purchasing team, and Chief Engineers.
**Tone:** Professional and concise, suitable for technical maritime personnel.

## Must answer
- part lookup
- price calculation
- order total
- lead time
- delivery estimate
- volume discount
- supplier terms
- approval limits
- procurement procedure
- freight quote

## Must refuse
- personal advice
- non-procurement queries
- legal advice
- financial planning beyond scope
- non-maritime procurement
- non-supplier related questions
- unverified external data

## Tool needs
- lookup part in catalogue
- calculate price with discount
- add freight to total
- compute delivery date from today
- retrieve supplier terms
- extract approval limits

## Knowledge sources

| Document | Type | Size | Covers |
|---|---|---|---|
| Spares_Procurement_Procedure.pdf | pdf | 2 pages, 483 words | Purpose, Raising a Requisition, Quotations, Approval Limits, OEM and Non OEM Parts, Critical Spares, Urgent Requisitions, Delivery and Receipt, Records |
| Supplier_Terms_Harbourline_Spares.pdf | pdf | 1 pages, 259 words | Volume Discounts, Urgent Orders, Delivery, Documentation, Warranty, Returns, Quotation Validity |
| Supplier_Terms_Poseidon_Marine.pdf | pdf | 1 pages, 296 words | Payment Terms, Volume Discounts, Urgent Orders, Delivery, Documentation, Warranty, Returns, Quotation Validity |
| spares_catalogue.csv | csv | 40 rows | part_number, description, equipment, maker, unit, unit_price_usd, stock_on_hand, lead_time_days, min_order_qty, supplier |

## Groundability check

| Topic | Status | Evidence | Source |
|---|---|---|---|
| part lookup | **supported** | part_number: ME-TC-4100; description: Turbocharger nozzle ring; equipment: Main engine; maker: ABB; unit: pc; unit_price_usd: 8950.00; stock | spares_catalogue.csv |
| price calculation | **supported** | computed by the 'calculator' tool from document data | spares_catalogue.csv |
| order total | **supported** | A volume discount is applied per purchase order on the total order value before freight. | Supplier_Terms_Harbourline_Spares.pdf, Supplier_Terms_Poseidon_Marine.pdf |
| lead time | **supported** | lead_time_days: 20 | spares_catalogue.csv |
| delivery estimate | **supported** | computed by the 'current_date' tool from document data | Supplier_Terms_Harbourline_Spares.pdf, Supplier_Terms_Poseidon_Marine.pdf |
| volume discount | **supported** | A volume discount is applied per purchase order on the total order value before freight. Orders of USD 5,000 or more receive a 5 percent dis | Supplier_Terms_Poseidon_Marine.pdf |
| supplier terms | **supported** | Invoices are payable net 30 days from the date of invoice. No early payment discount is offered. | Supplier_Terms_Harbourline_Spares.pdf |
| approval limits | **supported** | Approval limits apply to the total value of the purchase order after discounts. Up to USD 2,000: Chief Engineer for engine spares, or Master | Spares_Procurement_Procedure.pdf |
| procurement procedure | **supported** | This procedure governs how spare parts for the managed fleet are requisitioned, approved, ordered, delivered and received. | Spares_Procurement_Procedure.pdf |
| freight quote | **unsupported** |  |  |

## Flags raised at requirements stage
- ⚠ 'freight quote' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.

## Recommended clarifications or scope changes
- Either add a source document covering 'freight quote' or remove it from the scope.

## Known limitations
- Cannot answer: freight quote (not in the documents).
- Answers only from the supplied documents; no access to personal records or live systems.

## Uncertainties and assumptions
- Assumed (nobody answered): Are there any parts of the procurement procedure that the assistant should explicitly flag as out of scope (e.g., handling of critical spares or urgent requisitions)? -> All procedures are within scope; the assistant should handle critical and urgent requisitions as per the documents.
- Assumed (nobody answered): How should the assistant handle situations where the catalogue lacks a requested part or the supplier information is missing? -> Return a clear message indicating the part is unavailable and suggest contacting the procurement team.

## Clarifying interview

1. **Who are the primary users of the assistant—ship superintendents, purchasing staff, or both?**  
   _answers_file_: Technical superintendents, the purchasing team and Chief Engineers on board who email requests.
2. **What tone and level of formality should the assistant use when communicating with users?**  
   _answers_file_: Technical superintendents, the purchasing team and Chief Engineers on board who email requests.
3. **Are there any parts of the procurement procedure that the assistant should explicitly flag as out of scope (e.g., handling of critical spares or urgent requisitions)?**  
   _assumed_: All procedures are within scope; the assistant should handle critical and urgent requisitions as per the documents.
4. **How should the assistant handle situations where the catalogue lacks a requested part or the supplier information is missing?**  
   _assumed_: Return a clear message indicating the part is unavailable and suggest contacting the procurement team.
5. **Do we need the assistant to perform real-time freight rate lookups, or should it use a static rate table?**  
   _answers_file_: Yes, live freight rates would be very useful if possible.

**Approved:** True (human checkpoint disabled (unattended run))