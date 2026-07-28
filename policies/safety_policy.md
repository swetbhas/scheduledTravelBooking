# Safety Policy

## SP-1 Synthetic Data Only
The prototype may use only fake traveler names, fake contact information, simulated fare records, and demo identifiers. It must not use real personal, payment, passport, loyalty, or booking data.

## SP-2 Missing Or Inconsistent Data
If required traveler information is missing or flight data is inconsistent, the agent must stop and escalate instead of inventing a value.

## SP-3 Budget Boundary
If all available flights exceed the traveler's budget, the agent must escalate instead of recommending a booking.

## SP-4 Consequence Boundary
The agent must not send real alerts, process payment, alter traveler preferences, or book travel. Email, SMS, and booking actions are simulated on screen only.

## SP-5 Departure Timing Boundary
If less than two days remain before departure and no recommendation has been approved, the agent must escalate to human review.
