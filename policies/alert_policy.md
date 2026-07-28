# Alert Policy

## AP-1 Recommendation Limit
Each alert may include no more than two flight recommendations.

## AP-2 Simulated Channels
Email and SMS alerts are displayed as simulated messages inside the prototype. The app must not connect to real messaging tools.

## AP-3 Alert Frequency
Do not send a duplicate alert for the same flight within 24 hours. If the traveler does not respond within two days, send at most one simulated reminder.

## AP-4 Rejection Handling
If the traveler rejects a recommendation, the agent must record the rejection and resume monitoring. It must not complete a booking after rejection.
