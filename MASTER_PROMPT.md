# MASTER_PROMPT.md
Version: 1.0
Product: Scheduled Travel Booking Agent
Owner: Swetta Bhaskar
Status: Production Source of Truth
Last Updated: August 2026

---

# 1. Product Vision

Build an AI-powered travel monitoring agent that continuously searches for the best flight options based on a traveler's preferences, proactively recommends whether to Book Now or Wait, and always keeps the traveler in control before any booking action.

The product should reduce repeated manual searches while improving confidence in booking decisions.

---

# 2. Product Mission

Help budget-conscious travelers avoid repeatedly checking flight prices by automating:

- Fare monitoring
- Flight comparison
- Recommendation generation
- Alerting
- Human approval
- Simulated booking

The system MUST never make autonomous purchase decisions.

---

# 3. Primary User

Alex Morgan (Synthetic Traveler)

Origin:
Austin (AUS)

Destination:
Paris (CDG)

Travel Window:
July 30 – August 4

Travel Type:
International Leisure

Budget:
$2,000

Preferences

• Evening departure
• Maximum one stop
• One checked bag
• Window seat preferred

---

# 4. Product Goals

The system should

✓ continuously monitor prices

✓ recommend best flight

✓ explain recommendation

✓ reduce manual searches

✓ notify user

✓ wait for approval

✓ simulate booking

---

# 5. Success Metrics

Primary KPI

Manual flight searches avoided

Supporting KPIs

Time saved

Recommendation usefulness

Budget compliance

Policy compliance

Alert open rate

Approve rate

Reject rate

Recommendation accuracy

NPS

---

# 6. Human Control Principle

The traveler ALWAYS owns the final decision.

The AI may

✔ search

✔ compare

✔ rank

✔ explain

✔ recommend

✔ notify

The AI may NEVER

❌ purchase

❌ enter payment

❌ modify preferences

❌ submit booking

without explicit approval.

---

# 7. Core Workflow

1 User enters travel request

↓

Validate request

↓

Retrieve flight data

↓

Normalize flight options

↓

Apply ranking logic

↓

Determine:

Book Now

Wait

Best Partial Match

Escalate

↓

Generate explanation

↓

Generate Email

↓

Generate SMS

↓

Wait for approval

↓

If Approved

Simulate Booking

↓

Booking Confirmation

Else

Continue Monitoring

---

# 8. Monitoring Loop

The monitoring agent repeats flight evaluation periodically.

Current interval

Every 2 hours

Each run performs

Retrieve latest fares

Compare against history

Detect better opportunity

Generate recommendation

Respect duplicate alert rules

Stop if booking completed

---

# 9. Flight Ranking Priority

Current MVP Priority

1 Budget

2 Departure Time

3 Stops

4 Baggage

Future

Historical trend

Price prediction

Flexible dates

Airline loyalty

Flight duration

Weighted model (future)

Budget 40%

Departure 20%

Stops 15%

Baggage 10%

Duration 10%

Historical Trend 5%

---

# 10. Recommendation Types

BOOK NOW

WAIT

BEST PARTIAL MATCH

ESCALATE

Every recommendation MUST include rationale.

---

# 11. Required Inputs

Origin

Destination

Departure

Return

Traveler count

Budget

Stops

Departure preference

Baggage

Seat preference

Alert channel

---

# 12. Decision Rules

Recommend Book Now when

Flight satisfies required constraints

Within budget

Higher score than previous offers

Recommend Wait when

Historical comparison suggests waiting

No meaningful improvement

Recommend Partial Match when

Best available option violates only optional preferences

Escalate when

Missing data

Low confidence

No flights

Budget exceeded

Approval missing

---

# 13. Tool Definitions

Flight Search Tool

Retrieves synthetic flights.

Ranking Tool

Ranks flights.

Recommendation Engine

Produces recommendation.

Notification Service

Creates simulated Email and SMS.

Approval Service

Captures approval.

Booking Service

Creates simulated booking.

Scheduler

Triggers recurring monitoring.

---

# 14. Memory

Persist

Traveler preferences

Current trip

Last recommendation

Approval status

Alert history

Monitoring state

Never Persist

Payment information

Passport

Real customer data

Credentials

Secrets

---

# 15. Guardrails

Never fabricate booking confirmation.

Never fabricate payment.

Never imply purchase occurred.

Always disclose demo mode.

Use synthetic data only.

Never expose API keys.

Never access production systems.

---

# 16. Alert Rules

Maximum one reminder

Avoid duplicate alerts

Explain why recommendation changed

Include timestamp

Respect monitoring interval

---

# 17. Output Format

Recommendation

Book Now

Reason

Top Two Flights

Airline

Price

Stops

Departure

Arrival

Duration

Baggage

Confidence Score

Approve Button

Reject Button

---

# 18. Failure Handling

Missing Inputs

Ask user.

No Flights

Escalate.

Budget Exceeded

Recommend Wait.

Low Confidence

Escalate.

Approval Missing

Stop.

---

# 19. Coding Principles

Keep business rules separate.

Avoid hardcoded values.

Keep prompts reusable.

Separate UI from decision engine.

Prefer configuration over code.

Write readable functions.

Favor deterministic logic.

---

# 20. AI Prompting Principles

Never hallucinate.

Ground every recommendation.

Explain reasoning.

Cite business rules internally.

Do not invent traveler data.

Always respect approval boundary.

---

# 21. Developer Rules

Before coding

Read MASTER_PROMPT.md completely.

If implementation conflicts with this document

STOP

Explain discrepancy.

Ask before changing behavior.

Do not silently modify business rules.

---

# 22. Session Startup Prompt

Every coding session starts with:

"Read MASTER_PROMPT.md completely.

Treat it as the authoritative product specification.

Understand the workflow, business rules, safety constraints, tool responsibilities, and architecture before modifying any code.

If requirements conflict with implementation, explain the conflict and ask before making changes.

Do not change product behavior unless explicitly requested."

---

# 23. Version History

Version 1.0

Initial reconstruction from

• Product PRD

• Live prototype

• GitHub repository

• Deployment

• Demo walkthrough

This document becomes the canonical source of truth.