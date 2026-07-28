# Booking Policy

## BP-1 Required Search Inputs
The agent must have origin airport, destination airport, departure date, return date, number of travelers, budget, and approval status before preparing any simulated booking action.

## BP-2 Ranking Priorities
Rank eligible flights in this order: within budget, preferred departure window, maximum stops, baggage included, then shortest duration.

## BP-3 Book Now Criteria
The agent may recommend Book Now only when at least one available flight is within budget, meets the maximum stop limit, includes required baggage, and has verified data quality.

## BP-4 Best Partial Match Criteria
If no flight satisfies every traveler preference but at least one flight is still usable, the agent may recommend Best Partial Match. It must name the unmet criteria and wait for the traveler decision.

## BP-5 Approval Required
The agent must not complete even a simulated booking until the human approves the recommendation. Payment, passport details, and real booking systems are always out of scope.
