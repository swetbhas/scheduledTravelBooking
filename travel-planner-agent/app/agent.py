# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import calendar
import datetime as dt
import json
import re

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.models import Gemini
from google.genai import types

MODEL = "gemini-3.6-flash"

CITY_TO_AIRPORT = {
    "austin": "AUS",
    "aus": "AUS",
    "dallas": "DFW",
    "dfw": "DFW",
    "london": "LHR",
    "lhr": "LHR",
    "new york": "JFK",
    "nyc": "JFK",
    "los angeles": "LAX",
    "la": "LAX",
    "san francisco": "SFO",
    "sf": "SFO",
    "chicago": "ORD",
    "paris": "CDG",
    "tokyo": "HND",
}

MONTH_LOOKUP = {
    name.lower(): index for index, name in enumerate(calendar.month_name) if name
}
MONTH_LOOKUP.update(
    {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}
)
MONTH_NAME_PATTERN = "|".join(
    sorted((re.escape(name) for name in MONTH_LOOKUP), key=len, reverse=True)
)


def _normalize_airport(value: str) -> str:
    cleaned = value.strip().lower().strip(".,")
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return CITY_TO_AIRPORT.get(cleaned, value.strip().upper())


def _infer_year(month: int, day: int) -> int:
    today = dt.date.today()
    candidate = dt.date(today.year, month, day)
    if candidate <= today:
        return today.year + 1
    return today.year


def _parse_date(text: str, label: str) -> str | None:
    label_patterns = {
        "depart": r"(?:depart|departure|date\s+to\s+depart|depart\s+date)",
        "return": r"(?:return|return\s+date)",
    }
    label_pattern = label_patterns.get(label, re.escape(label))
    numeric_pattern = rf"{label_pattern}\s+(\d{{1,2}})[/-](\d{{1,2}})(?:[/-](\d{{2,4}}))?"
    numeric_match = re.search(numeric_pattern, text, flags=re.IGNORECASE)
    if numeric_match:
        month_text, day_text, year_text = numeric_match.groups()
        month = int(month_text)
        day = int(day_text)
        if year_text:
            year = int(year_text)
            if year < 100:
                year += 2000
        else:
            year = _infer_year(month, day)
        return dt.date(year, month, day).isoformat()

    pattern = (
        rf"{label_pattern}\s+([A-Za-z]+)\s+"
        rf"(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None

    month_name, day_text, year_text = match.groups()
    month = MONTH_LOOKUP[month_name.lower()]
    day = int(day_text)
    year = int(year_text) if year_text else _infer_year(month, day)
    return dt.date(year, month, day).isoformat()


def _parse_month_day_range(text: str) -> tuple[str | None, str | None]:
    day_pattern = r"(\d{1,2})(?:st|nd|rd|th)?"
    pattern = (
        rf"(?:from|between)\s+({MONTH_NAME_PATTERN})\s+{day_pattern}"
        rf"(?:,?\s+(\d{{4}}))?\s+(?:to|through|until|and|-)\s+"
        rf"(?:(?:({MONTH_NAME_PATTERN})\s+))?{day_pattern}(?:,?\s+(\d{{4}}))?"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None, None

    depart_month_name, depart_day_text, depart_year_text, return_month_name, return_day_text, return_year_text = match.groups()
    depart_month = MONTH_LOOKUP[depart_month_name.lower()]
    return_month = MONTH_LOOKUP[(return_month_name or depart_month_name).lower()]
    depart_day = int(depart_day_text)
    return_day = int(return_day_text)

    depart_year = (
        int(depart_year_text) if depart_year_text else _infer_year(depart_month, depart_day)
    )
    return_year = int(return_year_text) if return_year_text else depart_year
    depart_date = dt.date(depart_year, depart_month, depart_day)
    return_date = dt.date(return_year, return_month, return_day)
    if return_date < depart_date and not return_year_text:
        return_date = dt.date(return_year + 1, return_month, return_day)

    return depart_date.isoformat(), return_date.isoformat()


def _normalize_date_value(value) -> str | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return dt.datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            pass
    return text


def _parse_structured_request(request: str) -> dict | None:
    try:
        payload = json.loads(request)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    budget = payload.get("budget")
    if isinstance(budget, str):
        budget_match = re.search(r"\d+", budget)
        budget = int(budget_match.group(0)) if budget_match else None

    return {
        "origin": _normalize_airport(payload["origin"]) if payload.get("origin") else None,
        "destination": (
            _normalize_airport(payload["destination"])
            if payload.get("destination")
            else None
        ),
        "depart": _normalize_date_value(payload.get("depart")),
        "return": _normalize_date_value(payload.get("return")),
        "budget": budget,
        "nonstop": bool(payload.get("nonstop")),
        "flexibility": payload.get("flexibility"),
    }


def parse_travel_request(request: str) -> dict:
    """Extract structured travel-planning fields from an initial user request.

    Args:
        request: A natural-language travel request that can include origin,
            destination, departure and return dates, budget, nonstop preference,
            and date flexibility.

    Returns:
        A dictionary containing origin, destination, depart, return, budget,
        nonstop, and flexibility. Unknown values are returned as null.
    """
    structured_result = _parse_structured_request(request)
    if structured_result is not None:
        return structured_result

    origin = destination = None
    route_match = re.search(
        (
            r"(?:(?:travel|fly|go|trip|round\s+trip)\s+)?from\s+(.+?)\s+to\s+(.+?)"
            r"(?=\s+(?:date|depart|departure|return|budget|under|below|"
            r"less than|prefer|window|flex|nonstop|non-stop|nostop|"
            r"no stop|direct|up to|baggage|bag|luggage)\b|"
            rf"\s+from\s+(?:{MONTH_NAME_PATTERN})\b|\.|\n|$)"
        ),
        request,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if route_match:
        origin = _normalize_airport(route_match.group(1))
        destination = _normalize_airport(route_match.group(2))

    budget_match = re.search(
        r"(?:budget\s+)?(?:under|below|less than)\s+\$?(\d+)",
        request,
        re.IGNORECASE,
    )
    if not budget_match:
        budget_match = re.search(r"\bbudget\s+\$?(\d+)", request, re.IGNORECASE)
    if not budget_match:
        budget_match = re.search(r"\$(\d+)", request)

    flexibility_match = re.search(
        r"(?:window|flex(?:ibility)?)\s*(?:±|\+/-|plus or minus)?\s*(\d+)\s*days?",
        request,
        re.IGNORECASE,
    )

    range_depart, range_return = _parse_month_day_range(request)

    result = {
        "origin": origin,
        "destination": destination,
        "depart": _parse_date(request, "depart") or range_depart,
        "return": _parse_date(request, "return") or range_return,
        "budget": int(budget_match.group(1)) if budget_match else None,
        "nonstop": bool(
            re.search(r"\b(nonstop|non-stop|nostop|no stop|direct)\b", request, re.IGNORECASE)
        ),
        "flexibility": int(flexibility_match.group(1)) if flexibility_match else None,
    }
    return result


def parse_travel_request_json(request: str) -> str:
    """Return the extracted travel request as compact JSON."""
    return json.dumps(parse_travel_request(request), separators=(",", ":"))


def respond_with_parsed_travel_request(
    callback_context, llm_request: LlmRequest
) -> LlmResponse:
    """Return deterministic intake JSON as the final agent message."""
    latest_user_text = ""
    for content in reversed(llm_request.contents):
        if content.role != "user" or not content.parts:
            continue
        latest_user_text = "\n".join(part.text or "" for part in content.parts)
        if latest_user_text:
            break

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=parse_travel_request_json(latest_user_text))],
        ),
        turn_complete=True,
    )


root_agent = Agent(
    name="travel_planner_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a travel planner intake agent. Your only job is to convert the "
        "traveler's initial request into strict JSON with these keys: origin, "
        "destination, depart, return, budget, nonstop, flexibility. Use IATA "
        "airport codes when a city maps clearly to a known airport. Dates must "
        "be ISO-8601 YYYY-MM-DD. If the user omits the year, choose the next "
        "future occurrence of that month and day. Use null for missing fields. "
        "Call parse_travel_request_json, then return exactly the JSON string it "
        "produces and no markdown or explanation."
    ),
    tools=[parse_travel_request_json],
    before_model_callback=respond_with_parsed_travel_request,
)

app = App(
    root_agent=root_agent,
    name="app",
)
