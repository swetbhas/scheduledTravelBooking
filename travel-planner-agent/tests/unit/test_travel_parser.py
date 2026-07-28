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

from app.agent import parse_travel_request, parse_travel_request_json


def test_parse_initial_travel_conversation() -> None:
    request = """I need to travel from Dallas to London.
Depart July 10
Return July 18
Budget under $900
Prefer nonstop
Window +/-2 days"""

    assert parse_travel_request(request) == {
        "origin": "DFW",
        "destination": "LHR",
        "depart": "2027-07-10",
        "return": "2027-07-18",
        "budget": 900,
        "nonstop": True,
        "flexibility": 2,
    }


def test_parse_json_is_compact_and_stable() -> None:
    request = "I need to travel from DFW to LHR. Depart Jul 10 Return Jul 18 under $900 nonstop flex 2 days"

    assert parse_travel_request_json(request) == (
        '{"origin":"DFW","destination":"LHR","depart":"2027-07-10",'
        '"return":"2027-07-18","budget":900,"nonstop":true,"flexibility":2}'
    )


def test_parse_structured_json_request() -> None:
    request = (
        '{"origin":"Aus","destination":"Paris","depart":"08-09-2026",'
        '"return":"13-09-2026","budget":"3000","nonstop":false,'
        '"flexibility":null}'
    )

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-09-08",
        "return": "2026-09-13",
        "budget": 3000,
        "nonstop": False,
        "flexibility": None,
    }


def test_parse_route_with_date_to_depart_phrase() -> None:
    request = "travel from aus to Paris date to depart July 30"

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-07-30",
        "return": None,
        "budget": None,
        "nonstop": False,
        "flexibility": None,
    }


def test_parse_round_trip_from_phrase() -> None:
    request = (
        "I need a round trip from Austin to Paris. Depart July 30 2026. "
        "Return August 4 2026. Budget 3002. Up to 2 stops. Baggage included."
    )

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-07-30",
        "return": "2026-08-04",
        "budget": 3002,
        "nonstop": False,
        "flexibility": None,
    }


def test_parse_numeric_conversational_dates() -> None:
    request = (
        "I need a round trip from Austin to Paris. Depart 7/30/2026. "
        "Return 8/4/2026. Budget 3002. Up to 2 stops. Baggage included."
    )

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-07-30",
        "return": "2026-08-04",
        "budget": 3002,
        "nonstop": False,
        "flexibility": None,
    }


def test_parse_month_day_range_after_route() -> None:
    request = (
        "I would book a round trip from Austin to Paris from July 30th "
        "to August 4th with a budget of $3000"
    )

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-07-30",
        "return": "2026-08-04",
        "budget": 3000,
        "nonstop": False,
        "flexibility": None,
    }


def test_parse_compact_route_with_budget_and_nostop() -> None:
    request = (
        "travel from aus to Paris date to depart July 30 "
        "return Sep 13 budget 3000 nostop"
    )

    assert parse_travel_request(request) == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-07-30",
        "return": "2026-09-13",
        "budget": 3000,
        "nonstop": True,
        "flexibility": None,
    }
