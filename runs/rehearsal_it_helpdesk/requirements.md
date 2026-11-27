# Requirements: corvane-it-assistant

**Purpose:** Provide quick, policy‑based IT helpdesk support for Corvane Analytics employees in Bengaluru and Pune.
**Scope:** Answers are sourced exclusively from the supplied IT policies, device catalogue, and service desk guide. Live ticket or outage data is not available; the assistant will direct users to the Service Desk for such information.
**Audience:** All employees, interns, and contractors of Corvane Analytics in Bengaluru and Pune.
**Tone:** Friendly yet professional, concise and practical.

## Must answer
- password reset
- phishing email
- lost laptop
- raise ticket
- ticket status
- system outage
- hardware request
- software request
- accessory request
- monitor request

## Must refuse
- detailed troubleshooting
- non‑IT HR queries
- legal advice
- personal data requests
- live ticket updates
- live outage monitoring
- external vendor support

## Tool needs
- none (documents only)

## Knowledge sources

| Document | Type | Size | Covers |
|---|---|---|---|
| Hardware_and_Software_Requests.pdf | pdf | 2 pages, 414 words | Scope, Standard Laptop Entitlement, How to Request, Approvals, Software Requests, New Joiners, Accessories and Monitors, Returns and Exit, New Joiner Security N |
| IT_Service_Desk_Guide.pdf | pdf | 2 pages, 419 words | How to Contact the Service Desk, Ticket Priorities, Response and Resolution Targets, Escalation, Password Resets and Account Unlocks, Ticket Updates and Closure |
| Information_Security_Policy.pdf | pdf | 2 pages, 559 words | Purpose and Scope, Passwords and Multi Factor Authentication, Locking and Device Care, Lost or Stolen Devices, Removable Media and Personal Devices, Remote Work |
| device_catalogue.csv | csv | 15 rows | item_code, item, category, eligible_roles, price_inr, lead_time_days, approval_level, in_stock |

## Groundability check

| Topic | Status | Evidence | Source |
|---|---|---|---|
| password reset | **supported** | Use self service password reset at the login screen; it needs the Corvane Authenticator app. | IT_Service_Desk_Guide.pdf |
| phishing email | **supported** | Report suspicious emails with the Report Phishing button in Outlook. | Information_Security_Policy.pdf |
| lost laptop | **supported** | A lost or stolen laptop or phone must be reported to the Service Desk within 2 hours of discovery, by calling extension 4357 or the after ho | Information_Security_Policy.pdf |
| raise ticket | **supported** | Raise a ticket on the IT Self Service Portal, call extension 4357 (HELP), or email servicedesk@corvane.example. | IT_Service_Desk_Guide.pdf |
| ticket status | **unsupported** | the brief asks for live data ('the live status of their open tickets'); documents describe procedures, not current state |  |
| system outage | **unsupported** | the brief asks for live data ('whether any systems are down right now'); documents describe procedures, not current state |  |
| hardware request | **supported** | Submit requests through the IT Self Service Portal under Request Hardware or Request Software. Include the catalogue item code, quantity and | Hardware_and_Software_Requests.pdf |
| software request | **supported** | Submit requests through the IT Self Service Portal under Request Hardware or Request Software. Include the catalogue item code, quantity and | Hardware_and_Software_Requests.pdf |
| accessory request | **supported** | Accessories under INR 3,000, such as a mouse or keyboard, can be collected from the IT counter at either office without a portal request. | Hardware_and_Software_Requests.pdf |
| monitor request | **supported** | Each employee may have up to 2 external monitors. | Hardware_and_Software_Requests.pdf |

## Conflicting information across documents

- **Password change frequency**
  - Information_Security_Policy.pdf: "Passwords must be changed every 90 days; the system prompts you 7 days before expiry."
  - Hardware_and_Software_Requests.pdf: "Passwords must then be changed every 60 days."
  - why it is the same subject: Both passages define the mandatory password rotation interval for the same organization's accounts, creating a contradiction where a user would receive two different deadlines (90 vs 60 days) for the same action. (second model openai/gpt-oss-20b agreed)

## Flags raised at requirements stage
- ⚠ 'ticket status' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- ⚠ 'system outage' is requested by the brief but the documents do not support it. The agent will state that the documents do not cover it instead of answering.
- ⚠ Conflicting information on Password change frequency: Information_Security_Policy.pdf says "Passwords must be changed every 90 days; the system prompts you 7 days before expiry." while Hardware_and_Software_Requests.pdf says "Passwords must then be changed every 60 days.". The agent will present both and suggest confirming with the document owner.

## Recommended clarifications or scope changes
- Either add a source document covering 'ticket status' or remove it from the scope.
- Either add a source document covering 'system outage' or remove it from the scope.
- Ask the document owners which rule on Password change frequency is current, and fix the outdated document.

## Known limitations
- Cannot answer: ticket status (not in the documents).
- Cannot answer: system outage (not in the documents).
- Documents contradict each other on Password change frequency; answers cite both versions.
- Answers only from the supplied documents; no access to personal records or live systems.

## Uncertainties and assumptions
- Assumed (nobody answered): Who are the primary users of the assistant (e.g., all employees, contractors, interns) and are there any role‑specific restrictions on accessing certain information? -> All employees, interns, and contractors in Bengaluru and Pune.
- Assumed (nobody answered): What tone and style should the assistant adopt (formal, friendly, concise, etc.)? -> Friendly yet professional, concise and practical.
- Assumed (nobody answered): Which topics are explicitly out of scope for the assistant (e.g., detailed troubleshooting, non‑IT HR queries, or legal advice)? -> Anything not covered in the IT policies, device catalogue, or service desk guide.
- Assumed (nobody answered): How should the assistant handle requests for items not listed in the device catalogue or for which the user lacks eligibility? -> Inform the user that the item is unavailable or not eligible and direct them to the Service Desk for a business case.
- Assumed (nobody answered): What is the expected method for providing live status of open tickets and system outages (e.g., integration with ticketing system, real‑time monitoring feeds)? -> No live system or integration is available. The assistant answers only from the supplied documents, says plainly when something needs live data or personal records, and points to the right team or channel.

## Clarifying interview

1. **Who are the primary users of the assistant (e.g., all employees, contractors, interns) and are there any role‑specific restrictions on accessing certain information?**  
   _assumed_: All employees, interns, and contractors in Bengaluru and Pune.
2. **What tone and style should the assistant adopt (formal, friendly, concise, etc.)?**  
   _assumed_: Friendly yet professional, concise and practical.
3. **Which topics are explicitly out of scope for the assistant (e.g., detailed troubleshooting, non‑IT HR queries, or legal advice)?**  
   _assumed_: Anything not covered in the IT policies, device catalogue, or service desk guide.
4. **How should the assistant handle requests for items not listed in the device catalogue or for which the user lacks eligibility?**  
   _assumed_: Inform the user that the item is unavailable or not eligible and direct them to the Service Desk for a business case.
5. **What is the expected method for providing live status of open tickets and system outages (e.g., integration with ticketing system, real‑time monitoring feeds)?**  
   _assumed_: No live system or integration is available. The assistant answers only from the supplied documents, says plainly when something needs live data or personal records, and points to the right team or channel.

**Approved:** True (human checkpoint disabled (unattended run))