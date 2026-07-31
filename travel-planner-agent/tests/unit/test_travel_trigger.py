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

import json

from fastapi.testclient import TestClient

from app.app_utils.codex_credentials import load_shared_codex_credentials
from app.fast_api_app import app
from app.travel_trigger import (
    TravelTriggerRequest,
    curate_travel_request,
    render_travel_email,
    trigger_travel_planner,
)

REQUEST = """I need to travel from Dallas to London.
Depart July 10
Return July 18
Budget under $900
Prefer nonstop
Window +/-2 days"""


def test_curation_extracts_travel_fields() -> None:
    assert curate_travel_request(REQUEST) == {
        "origin": "DFW",
        "destination": "LHR",
        "depart": "2027-07-10",
        "return": "2027-07-18",
        "budget": 900,
        "nonstop": True,
        "flexibility": 2,
    }


def test_rendering_builds_preview_without_sending() -> None:
    preview = render_travel_email(curate_travel_request(REQUEST))

    assert preview.subject == "Travel plan preview: DFW to LHR"
    assert "Origin: DFW" in preview.text
    assert "<td>LHR</td>" in preview.html


def test_trigger_dry_run_never_sends_email() -> None:
    response = trigger_travel_planner(TravelTriggerRequest(request=REQUEST, dry_run=True))

    assert response.dry_run is True
    assert response.sent is False
    assert response.skipped_reason == "dry_run"
    assert response.parsed["budget"] == 900


def test_trigger_endpoint_is_scheduler_callable() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/triggers/travel-intake",
        json={"request": REQUEST, "dry_run": True, "recipient": "preview@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["skipped_reason"] == "dry_run"
    assert payload["parsed"]["origin"] == "DFW"
    assert payload["preview"]["subject"] == "Travel plan preview: DFW to LHR"


def test_root_serves_traveler_form() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Voyage" in response.text
    assert "travel booking" in response.text
    assert "Alex" in response.text
    assert 'aria-label="Mic"' in response.text
    assert "Start voice" not in response.text
    assert "/api/traveler/request" in response.text
    assert "/api/traveler/chat" in response.text
    assert "An email/SMS will be send" in response.text
    assert "<th>Reason</th>" in response.text
    assert "<th>Outbound</th>" in response.text
    assert "<th>Return</th>" in response.text
    assert "<th>Source</th>" not in response.text
    assert "Booking/API Source" not in response.text
    assert 'aria-label="Booking"' in response.text
    assert "Accept" in response.text
    assert "Reject" in response.text


def test_traveler_form_submission_parses_request() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/request",
        json={
            "origin": "AUS",
            "destination": "CDG",
            "depart": "2026-09-08",
            "return_date": "2026-09-13",
            "budget": 3000,
            "max_stops": 1,
            "baggage_included": True,
            "traveler_email": "traveler@example.com",
            "recipient_email": "er.shwetabhaskar@gmail.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"] == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-09-08",
        "return": "2026-09-13",
        "budget": 3000,
        "nonstop": False,
        "flexibility": None,
    }
    assert payload["traveler_email"] == "traveler@example.com"
    assert payload["preferences"] == {"max_stops": 1, "baggage_included": True}
    assert payload["next_step"] == {
        "monitor": "aus-to-cdg-synthetic-fare-monitor",
        "status": "sent",
        "immediate_run": "completed",
        "schedule": "Every 2 hours",
        "timezone": "America/Chicago",
        "handoff_url": "/api/monitor/latest-request",
    }
    assert payload["monitor_result"]["run_timing"].startswith("Immediate once")
    assert payload["monitor_result"]["schedule"] == "Every 2 hours"

    handoff_response = client.get("/api/monitor/latest-request")

    assert handoff_response.status_code == 200
    handoff_payload = handoff_response.json()
    assert handoff_payload["status"] == "ready"
    assert handoff_payload["monitor_id"] == "aus-to-cdg-synthetic-fare-monitor"
    assert handoff_payload["source"] == "travel-planner-agent"
    assert handoff_payload["criteria"] == {
        "origin": "AUS",
        "destination": "CDG",
        "depart": "2026-09-08",
        "return": "2026-09-13",
        "budget": 3000,
        "nonstop": False,
        "flexibility": None,
        "max_stops": 1,
        "baggage_included": True,
    }
    assert handoff_payload["traveler_email"] == "traveler@example.com"
    assert handoff_payload["immediate_result"]["run_timing"].startswith("Immediate once")


def test_traveler_form_submission_runs_immediate_exact_fare_monitor() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/request",
        json={
            "origin": "AUS",
            "destination": "CDG",
            "depart": "2026-08-20",
            "return_date": "2026-08-25",
            "budget": 3002,
            "max_stops": 2,
            "baggage_included": True,
            "recipient_email": "er.shwetabhaskar@gmail.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_result"]["status"] == "STOP CONDITION MET"
    assert payload["monitor_result"]["rows"][0]["flight_id"] == "FL-DEMO-526"
    assert payload["monitor_result"]["rows"][0]["return_depart_datetime"].startswith("2026-08-25T")
    assert payload["monitor_result"]["rows"][0]["return_arrive_datetime"].startswith("2026-08-25T")
    assert "Pioneer Wings" in payload["monitor_result"]["codex_table_markdown"]
    assert "| Airline | Dates | Outbound | Return | Stops | Price | Baggage | Reason |" in payload["monitor_result"]["codex_table_markdown"]
    assert "CDG " in payload["monitor_result"]["codex_table_markdown"]
    assert " -> AUS " in payload["monitor_result"]["codex_table_markdown"]
    assert "Booking/API Source" not in payload["monitor_result"]["codex_table_markdown"]
    assert "data/flight_snapshots.csv" not in payload["monitor_result"]["codex_table_markdown"]
    assert payload["next_step"]["immediate_run"] == "completed"
    assert payload["next_step"]["schedule"] == "Every 2 hours"


def test_traveler_form_submission_runs_july_happy_path_monitor() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/request",
        json={
            "origin": "AUS",
            "destination": "CDG",
            "depart": "2026-07-30",
            "return_date": "2026-08-04",
            "budget": 2000,
            "max_stops": 1,
            "baggage_included": True,
            "recipient_email": "er.shwetabhaskar@gmail.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_result"]["status"] == "STOP CONDITION MET"
    assert payload["monitor_result"]["rows"][0]["case_id"] == "CASE-1016"
    assert payload["monitor_result"]["rows"][0]["return_depart_datetime"].startswith("2026-08-04T")
    assert payload["monitor_result"]["rows"][0]["return_arrive_datetime"].startswith("2026-08-04T")
    assert "2026-07-30 to 2026-08-04" in payload["monitor_result"]["codex_table_markdown"]


def test_traveler_chat_submission_parses_request_and_runs_monitor() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/chat",
        json={
            "request": (
                "I need a round trip from Austin to Paris. Depart August 20 2026. "
                "Return August 25 2026. Budget 3002. Up to 2 stops. Baggage included."
            ),
            "traveler_email": "traveler@example.com",
            "recipient_email": "er.shwetabhaskar@gmail.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intake_mode"] == "chat"
    assert payload["parsed"]["origin"] == "AUS"
    assert payload["parsed"]["destination"] == "CDG"
    assert payload["parsed"]["depart"] == "2026-08-20"
    assert payload["parsed"]["return"] == "2026-08-25"
    assert payload["preferences"] == {"max_stops": 2, "baggage_included": True}
    assert payload["monitor_result"]["status"] == "STOP CONDITION MET"


def test_traveler_chat_submission_parses_numeric_dates() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/chat",
        json={
            "request": (
                "I need a round trip from Austin to Paris. Depart 8/20/2026. "
                "Return 8/25/2026. Budget 3002. Up to 2 stops. Baggage included."
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["depart"] == "2026-08-20"
    assert payload["parsed"]["return"] == "2026-08-25"
    assert payload["monitor_result"]["status"] == "STOP CONDITION MET"


def test_traveler_chat_submission_parses_month_day_range() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/traveler/chat",
        json={
            "request": (
                "I would book a round trip from Austin to Paris from August 20th "
                "to August 25th with a budget of $3000"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["origin"] == "AUS"
    assert payload["parsed"]["destination"] == "CDG"
    assert payload["parsed"]["depart"] == "2026-08-20"
    assert payload["parsed"]["return"] == "2026-08-25"


def test_shared_codex_credentials_load_from_runtime_path(tmp_path, monkeypatch) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"email_provider": "test"}), encoding="utf-8")
    monkeypatch.setenv("CODEX_SHARED_CREDENTIALS_PATH", str(credentials_path))

    assert load_shared_codex_credentials() == {"email_provider": "test"}
