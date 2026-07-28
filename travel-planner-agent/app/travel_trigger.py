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

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import parse_travel_request
from app.app_utils.codex_credentials import load_shared_codex_credentials


class TravelTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str = Field(min_length=1)
    recipient: str | None = None
    dry_run: bool = True


class TravelEmailPreview(BaseModel):
    subject: str
    text: str
    html: str


class TravelTriggerResponse(BaseModel):
    dry_run: bool
    sent: bool
    parsed: dict[str, Any]
    preview: TravelEmailPreview
    credentials_loaded: bool
    skipped_reason: str | None = None


def curate_travel_request(request: str) -> dict[str, Any]:
    """Curate a raw travel request into deterministic planning fields."""
    return parse_travel_request(request)


def render_travel_email(parsed: dict[str, Any]) -> TravelEmailPreview:
    """Render the curated travel fields as an email preview."""
    origin = parsed.get("origin") or "UNKNOWN"
    destination = parsed.get("destination") or "UNKNOWN"
    subject = f"Travel plan preview: {origin} to {destination}"

    lines = [
        "Travel request preview",
        "",
        f"Origin: {parsed.get('origin')}",
        f"Destination: {parsed.get('destination')}",
        f"Depart: {parsed.get('depart')}",
        f"Return: {parsed.get('return')}",
        f"Budget: {parsed.get('budget')}",
        f"Nonstop: {parsed.get('nonstop')}",
        f"Flexibility: {parsed.get('flexibility')} days",
    ]
    rows = "\n".join(lines)
    html_rows = "".join(
        f"<tr><th>{label}</th><td>{parsed.get(key)}</td></tr>"
        for label, key in [
            ("Origin", "origin"),
            ("Destination", "destination"),
            ("Depart", "depart"),
            ("Return", "return"),
            ("Budget", "budget"),
            ("Nonstop", "nonstop"),
            ("Flexibility", "flexibility"),
        ]
    )
    return TravelEmailPreview(
        subject=subject,
        text=rows,
        html=f"<h1>Travel request preview</h1><table>{html_rows}</table>",
    )


def trigger_travel_planner(payload: TravelTriggerRequest) -> TravelTriggerResponse:
    """Run the scheduler-callable trigger path.

    Dry runs never send email. Non-dry-run delivery is intentionally gated on
    runtime credentials and can be wired to a concrete provider later.
    """
    parsed = curate_travel_request(payload.request)
    preview = render_travel_email(parsed)
    credentials = load_shared_codex_credentials(required=not payload.dry_run)

    if payload.dry_run:
        return TravelTriggerResponse(
            dry_run=True,
            sent=False,
            parsed=parsed,
            preview=preview,
            credentials_loaded=bool(credentials),
            skipped_reason="dry_run",
        )

    return TravelTriggerResponse(
        dry_run=False,
        sent=False,
        parsed=parsed,
        preview=preview,
        credentials_loaded=bool(credentials),
        skipped_reason="email_delivery_not_configured",
    )
