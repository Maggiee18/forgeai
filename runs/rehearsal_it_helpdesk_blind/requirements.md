# Requirements: corvane-it-assistant

**Purpose:** Provide quick, policy‑based answers to Corvane Analytics employees about IT support, device requests, and security, while directing unresolved issues to the Service Desk.
**Scope:** Answers are drawn solely from the IT Service Desk Guide, Hardware and Software Request Procedure, Information Security Policy, and the device catalogue. The assistant also reports live ticket status and system outages via the ticketing and monitoring APIs.
**Audience:** All employees, interns, and contractors in Bengaluru and Pune.
**Tone:** Friendly yet professional, concise and practical.

## Must answer
- password reset
- phishing email
- lost laptop
- raise ticket
- ticket response time
- hardware request procedure
- software request procedure
- device catalogue prices
- approval levels
- system outage status

## Must refuse
- detailed troubleshooting beyond policy
- non‑IT HR queries
- legal advice
- personal data requests
- requests for items not in catalogue
- requests for non‑eligible roles
- requests for external vendor information

## Tool needs
- lookup item in device catalogue
- fetch ticket status from API
- fetch system outage status from monitoring API

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
| ticket response time | **supported** | Priority 1: response within 15 minutes, resolution target 4 hours, worked around the clock. Priority 2: response within 30 minutes, resoluti | IT_Service_Desk_Guide.pdf |
| hardware request procedure | **supported** | Submit requests through the IT Self Service Portal under Request Hardware or Request Software. Include the catalogue item code, quantity and | Hardware_and_Software_Requests.pdf |
| software request procedure | **supported** | Anything not in the Company Portal must be requested under the Hardware and Software Request Procedure (IT-PRC-03) and pass a security revie | Information_Security_Policy.pdf |
| device catalogue prices | **supported** | price_inr: 2400 | device_catalogue.csv |
| approval levels | **supported** | approval_level: reporting manager | device_catalogue.csv |
| system outage status | **supported** | For outages affecting more than 25 users, the Service Desk declares a major incident, posts updates on the IT Status page every 30 minutes a | IT_Service_Desk_Guide.pdf |

## Known limitations
- Answers only from the supplied documents; no access to personal records or live systems.

## Uncertainties and assumptions
- Assumed (nobody answered): Who are the primary users of the assistant (e.g., all employees, contractors, interns) and are there any role‑specific restrictions on accessing certain information? -> All employees, interns, and contractors in Bengaluru and Pune.
- Assumed (nobody answered): What tone and style should the assistant adopt (formal, friendly, concise, etc.)? -> Friendly yet professional, concise and practical.
- Assumed (nobody answered): Which topics are explicitly out of scope for the assistant (e.g., detailed troubleshooting, non‑IT HR queries, or legal advice)? -> Anything not covered in the IT policies, device catalogue, or service desk guide.
- Assumed (nobody answered): How should the assistant handle requests for items not listed in the device catalogue or for which the user lacks eligibility? -> Inform the user that the item is unavailable or not eligible and direct them to the Service Desk for a business case.
- Assumed (nobody answered): What is the expected method for providing live status of open tickets and system outages (e.g., integration with ticketing system, real‑time monitoring feeds)? -> Use the existing ticketing system API to fetch ticket status and a monitoring dashboard API for system outages.

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
   _assumed_: Use the existing ticketing system API to fetch ticket status and a monitoring dashboard API for system outages.

**Approved:** True (human checkpoint disabled (unattended run))