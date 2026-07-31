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

import contextlib
import csv
import datetime as dt
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging
from pydantic import BaseModel, ConfigDict, Field

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.typing import Feedback
from app.travel_trigger import TravelTriggerRequest, trigger_travel_planner

load_dotenv()
try:
    _, project_id = google.auth.default()
except google.auth.exceptions.DefaultCredentialsError:
    project_id = None


class _LocalLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def log_struct(self, payload: dict[str, Any], severity: str = "INFO") -> None:
        level = getattr(logging, severity, logging.INFO)
        self._logger.log(level, "%s", payload)


class TravelerRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    depart: str = Field(min_length=1)
    return_date: str | None = None
    budget: int | None = Field(default=None, ge=0)
    max_stops: int | None = Field(default=None, ge=0)
    baggage_included: bool = False
    flexibility: int | None = Field(default=None, ge=0)
    traveler_email: str | None = None
    recipient_email: str | None = None


class TravelerChatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str = Field(min_length=1)
    traveler_email: str | None = None
    recipient_email: str | None = None


latest_monitor_request: dict[str, Any] | None = None

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
STATIC_DIR = PROJECT_DIR / "app" / "static"


try:
    logging_client = google_cloud_logging.Client(project=project_id) if project_id else None
    logger = logging_client.logger(__name__) if logging_client else _LocalLogger()
except Exception:
    logger = _LocalLogger()

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=True,
    lifespan=lifespan,
)
app.title = "travel-planner-agent"
app.description = "API for interacting with the Agent travel-planner-agent"
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def _traveler_form_html() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Voyage</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      color-scheme: light;
      --bg: #063f46;
      --ink: #102631;
      --muted: #577185;
      --line: rgba(0, 109, 119, 0.24);
      --accent: #006d77;
      --accent-dark: #00515a;
      --sun: #ffb703;
      --coral: #ef476f;
      --panel: rgba(232, 246, 244, 0.9);
      --field: rgba(255, 250, 238, 0.94);
      --soft: rgba(255, 183, 3, 0.14);
      --ok: #12805c;
      --shadow: 0 24px 70px rgba(2, 26, 35, 0.26);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Plus Jakarta Sans", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(180deg, rgba(5, 41, 47, 0.42), rgba(5, 41, 47, 0.55)),
        url("/assets/images/mountain-lake.png") center center / cover no-repeat fixed,
        radial-gradient(circle at 12% 8%, rgba(255, 183, 3, 0.22), transparent 31%),
        radial-gradient(circle at 88% 12%, rgba(239, 71, 111, 0.24), transparent 27%),
        linear-gradient(135deg, #063f46 0%, #006d77 48%, #0d5f68 100%),
        var(--bg);
      color: var(--ink);
      min-height: 100vh;
    }
    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 34px 0 140px;
    }
    header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: end;
      margin-bottom: 22px;
      padding: 26px;
      color: white;
      background:
        linear-gradient(135deg, rgba(0, 74, 83, 0.98), rgba(0, 109, 119, 0.9) 54%, rgba(239, 71, 111, 0.88)),
        #006d77;
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    h1 {
      margin: 0;
      font-family: "Instrument Serif", Georgia, serif;
      font-size: clamp(2.15rem, 4vw, 4.6rem);
      line-height: 1.05;
      letter-spacing: 0;
    }
    .eyebrow {
      margin: 0 0 8px;
      color: rgba(255, 255, 255, 0.78);
      font-family: "Instrument Serif", Georgia, serif;
      font-size: 1.35rem;
      font-style: italic;
      font-weight: 400;
      text-transform: none;
    }
    .subhead {
      margin: 12px 0 0;
      max-width: 720px;
      color: rgba(255, 255, 255, 0.84);
      font-size: 1rem;
      line-height: 1.55;
    }
    .status {
      color: #08323a;
      background: var(--sun);
      border: 1px solid rgba(255, 255, 255, 0.42);
      border-radius: 999px;
      padding: 9px 13px;
      font-weight: 700;
      white-space: nowrap;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.16);
    }
    .layout {
      display: grid;
      gap: 20px;
      align-items: start;
    }
    form, .result {
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.38);
      border-radius: 8px;
      padding: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }
    form {
      background:
        linear-gradient(135deg, rgba(232, 246, 244, 0.88), rgba(255, 250, 238, 0.7)),
        url("/assets/images/vacation-beach.png");
      background-size: cover;
      background-position: center;
    }
    .result {
      background:
        linear-gradient(135deg, rgba(232, 246, 244, 0.84), rgba(255, 250, 238, 0.7)),
        url("/assets/images/mountain-lake.png");
      background-size: cover;
      background-position: center;
    }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 18px;
    }
    h2 {
      margin: 0;
      font-size: 1.22rem;
      letter-spacing: 0;
    }
    .flash-line {
      grid-column: 1 / -1;
      margin: 0 0 16px;
      color: var(--coral);
      font-family: "Instrument Serif", Georgia, serif;
      font-size: clamp(1.7rem, 3vw, 2.7rem);
      font-style: italic;
      line-height: 1;
    }
    .hero-flash {
      margin: 6px 0 0;
      color: var(--sun);
      text-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }
    .mini-pill {
      color: var(--accent-dark);
      background: rgba(255, 183, 3, 0.2);
      border: 1px solid rgba(0, 109, 119, 0.18);
      border-radius: 999px;
      padding: 6px 9px;
      font-size: 0.78rem;
      font-weight: 800;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    label {
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 700;
    }
    input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 13px 14px;
      color: var(--ink);
      font: inherit;
      background: white;
      background: var(--field);
      box-shadow: 0 8px 20px rgba(25, 43, 66, 0.05);
    }
    input:focus, select:focus {
      border-color: var(--accent);
      outline: 3px solid rgba(9, 105, 218, 0.14);
    }
    .full { grid-column: 1 / -1; }
    .chat-box {
      display: grid;
      gap: 12px;
      padding: 14px;
      border: 1px solid rgba(0, 109, 119, 0.18);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(0, 109, 119, 0.18), rgba(255, 183, 3, 0.18), rgba(239, 71, 111, 0.08));
    }
    textarea {
      width: 100%;
      min-height: 112px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 13px 14px;
      color: var(--ink);
      font: inherit;
      line-height: 1.5;
      background: var(--field);
      box-shadow: 0 8px 20px rgba(25, 43, 66, 0.05);
    }
    textarea:focus {
      border-color: var(--accent);
      outline: 3px solid rgba(9, 105, 218, 0.14);
    }
    .chat-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .secondary-button {
      background: rgba(255, 250, 238, 0.96);
      color: var(--accent-dark);
      border: 1px solid rgba(0, 109, 119, 0.24);
      box-shadow: none;
    }
    .icon-button {
      width: 46px;
      height: 46px;
      display: inline-grid;
      place-items: center;
      padding: 0;
      font-size: 0;
      vertical-align: middle;
    }
    .icon-button svg {
      width: 20px;
      height: 20px;
    }
    .voice-button.recording {
      background: linear-gradient(135deg, var(--coral), #8f2d56);
      color: white;
    }
    .voice-status {
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 700;
    }
    .alex-widget {
      position: fixed;
      inset: auto 24px 24px auto;
      z-index: 20;
      width: min(390px, calc(100vw - 48px));
    }
    .alex-card {
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.42);
      border-radius: 8px;
      background: rgba(232, 246, 244, 0.94);
      box-shadow: 0 24px 70px rgba(2, 26, 35, 0.34);
      backdrop-filter: blur(14px);
    }
    .alex-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 14px;
      color: white;
      background: linear-gradient(135deg, var(--accent-dark), var(--accent));
    }
    .alex-header strong {
      font-size: 1rem;
    }
    .alex-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--sun);
      box-shadow: 0 0 0 4px rgba(255, 183, 3, 0.2);
    }
    .alex-card .chat-box {
      border: 0;
      border-radius: 0;
      background: linear-gradient(135deg, rgba(0, 109, 119, 0.12), rgba(255, 183, 3, 0.15), rgba(239, 71, 111, 0.08));
    }
    .alex-card textarea {
      min-height: 122px;
    }
    .toggle {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 45px;
      color: var(--ink);
      background: rgba(255, 183, 3, 0.22);
      border: 1px solid rgba(255, 183, 3, 0.28);
      border-radius: 6px;
      padding: 10px 12px;
    }
    .toggle input { width: 18px; height: 18px; }
    button {
      border: 0;
      border-radius: 6px;
      background: linear-gradient(135deg, var(--accent), var(--coral));
      color: white;
      font: inherit;
      font-weight: 800;
      padding: 13px 18px;
      cursor: pointer;
      box-shadow: 0 16px 30px rgba(0, 109, 119, 0.24);
    }
    button:hover { filter: brightness(0.96); }
    .actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 18px;
    }
    .hint {
      color: var(--muted);
      font-size: 0.9rem;
      margin: 0;
    }
    .output {
      min-height: 260px;
      color: var(--ink);
    }
    .empty-state {
      display: grid;
      place-items: center;
      min-height: 300px;
      border: 1px dashed #b9c7d6;
      border-radius: 8px;
      color: var(--muted);
      text-align: center;
      padding: 24px;
      background: rgba(255, 250, 238, 0.66);
    }
    .result-banner {
      display: grid;
      gap: 6px;
      margin-bottom: 16px;
      padding: 14px;
      border-radius: 8px;
      color: white;
      background: linear-gradient(135deg, var(--ok), var(--accent));
    }
    .result-banner strong { font-size: 1.05rem; }
    .approval-note {
      margin-top: 12px;
      border: 1px solid rgba(0, 109, 119, 0.2);
      border-left: 4px solid var(--sun);
      border-radius: 8px;
      background: rgba(255, 250, 238, 0.9);
      color: var(--accent-dark);
      padding: 12px 14px;
      font-size: 0.9rem;
      font-weight: 800;
      line-height: 1.45;
    }
    .booking-section {
      display: grid;
      gap: 12px;
      margin-top: 14px;
      border: 1px solid rgba(0, 109, 119, 0.2);
      border-radius: 8px;
      background: rgba(232, 246, 244, 0.9);
      padding: 14px;
    }
    .booking-section h3 {
      margin: 0;
      color: var(--ink);
      font-size: 1.04rem;
      letter-spacing: 0;
    }
    .booking-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .booking-choice {
      width: 100%;
    }
    .reject-button {
      background: linear-gradient(135deg, #8f2d56, var(--coral));
    }
    .booking-confirm {
      width: 100%;
      background: linear-gradient(135deg, var(--ok), var(--accent));
    }
    .booking-status {
      min-height: 1.25rem;
      color: var(--accent-dark);
      font-size: 0.88rem;
      font-weight: 800;
      line-height: 1.4;
    }
    .is-hidden {
      display: none;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(255, 250, 238, 0.92);
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 800;
      margin-bottom: 4px;
    }
    .metric strong {
      font-size: 1rem;
      overflow-wrap: anywhere;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: rgba(255, 250, 238, 0.96);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      display: block;
      overflow-x: auto;
    }
    th, td {
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    th {
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      background: rgba(0, 109, 119, 0.1);
    }
    tr:last-child td { border-bottom: 0; }
    .price {
      color: var(--ok);
      font-weight: 900;
    }
    .json-details {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #101828;
      color: #e6edf7;
      padding: 12px;
      max-height: 260px;
      overflow: auto;
      font-size: 0.82rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    @media (max-width: 820px) {
      header { display: block; }
      header { padding: 22px; }
      .status { display: inline-block; margin-top: 14px; }
      .grid { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: 1fr; }
      .actions { display: grid; justify-items: stretch; }
      .chat-actions { display: grid; }
      .alex-widget {
        inset: auto 16px 16px auto;
        width: min(360px, calc(100vw - 32px));
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <p class="eyebrow">travel booking</p>
        <h1>Voyage</h1>
        <p class="flash-line hero-flash">Let's go places</p>
        <p class="subhead">Send a trip request, run the fare monitor immediately, then keep the scheduled watch active every two hours.</p>
      </div>
      <div class="status">Live on Cloud Run</div>
    </header>
    <section class="layout">
      <form id="travel-form">
        <div class="panel-title">
          <h2>Trip</h2>
          <span class="mini-pill">Immediate + every 2h</span>
        </div>
        <div class="grid">
          <label>Origin
            <input name="origin" value="AUS" autocomplete="off" required>
          </label>
          <label>Destination
            <input name="destination" value="CDG" autocomplete="off" required>
          </label>
          <label>Depart
            <input name="depart" type="date" value="2026-08-20" required>
          </label>
          <label>Return
            <input name="return_date" type="date" value="2026-08-25">
          </label>
          <label>Budget
            <input name="budget" type="number" min="0" value="3000">
          </label>
          <label>Maximum stops
            <select name="max_stops">
              <option value="1" selected>1 stop</option>
              <option value="0">Nonstop only</option>
              <option value="2">Up to 2 stops</option>
            </select>
          </label>
          <label>Flexibility in days
            <input name="flexibility" type="number" min="0" value="1">
          </label>
          <label>Traveler email
            <input name="traveler_email" type="email" value="traveler@example.com">
          </label>
          <label class="full">Notification recipient
            <input name="recipient_email" type="email" value="er.shwetabhaskar@gmail.com">
          </label>
          <label class="toggle full">
            <input name="baggage_included" type="checkbox" checked>
            1 checked bag included
          </label>
        </div>
        <div class="actions">
          <p class="hint">Launch an intelligent continuous search that starts immediately and proactively scans for the best flight options every two hours based on the traveler's preference.</p>
          <button type="submit">Fare monitor</button>
        </div>
      </form>
      <aside class="result" aria-live="polite">
        <div class="panel-title">
          <h2>Monitor Result</h2>
          <span class="mini-pill">Journey</span>
        </div>
        <div id="output" class="output">
          <div class="empty-state">Fill out the trip and run the monitor. Results will appear here as a fare table.</div>
        </div>
      </aside>
      <section id="booking-section" class="booking-section is-hidden" aria-label="Booking" aria-hidden="true">
        <h3>Booking</h3>
        <div class="booking-actions">
          <button id="booking-accept" class="booking-choice accept-button" type="button">Accept</button>
          <button id="booking-reject" class="booking-choice reject-button" type="button">Reject</button>
        </div>
        <button id="booking-confirm" class="booking-confirm is-hidden" type="button" aria-hidden="true">Booking</button>
        <div id="booking-status" class="booking-status" aria-live="polite"></div>
      </section>
    </section>
  </main>
  <section class="alex-widget" aria-label="Alex chat assistant">
    <div class="alex-card">
      <div class="alex-header">
        <strong>Alex</strong>
        <span class="alex-dot" aria-hidden="true"></span>
      </div>
      <div class="chat-box">
        <label>Request
          <textarea id="chat-request" placeholder="I need a round trip from Austin to Paris. Depart 8/20/2026. Return 8/25/2026. Budget 3002. Up to 2 stops. Baggage included."></textarea>
        </label>
        <div class="chat-actions">
          <span id="voice-status" class="voice-status">Use text, voice, or the manual fields.</span>
          <div>
            <button id="voice-button" class="secondary-button voice-button icon-button" type="button" aria-label="Mic" title="Mic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                <path d="M12 19v3"></path>
              </svg>
            </button>
            <button id="chat-submit" class="secondary-button" type="button">Submit</button>
          </div>
        </div>
      </div>
    </div>
  </section>
  <script>
    const form = document.querySelector("#travel-form");
    const output = document.querySelector("#output");
    const chatRequest = document.querySelector("#chat-request");
    const chatSubmit = document.querySelector("#chat-submit");
    const voiceButton = document.querySelector("#voice-button");
    const voiceStatus = document.querySelector("#voice-status");
    const bookingSection = document.querySelector("#booking-section");
    const acceptButton = document.querySelector("#booking-accept");
    const rejectButton = document.querySelector("#booking-reject");
    const bookingButton = document.querySelector("#booking-confirm");
    const bookingStatus = document.querySelector("#booking-status");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const emptyMonitorHtml = '<div class="empty-state">Fill out the trip and run the monitor. Results will appear here as a fare table.</div>';
    let recognition = null;

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function formatTime(value) {
      if (!value) return "";
      return value.slice(11, 16);
    }

    function formatDateRange(depart, returnDate) {
      if (depart && returnDate) return `${depart} to ${returnDate}`;
      if (depart) return depart;
      if (returnDate) return returnDate;
      return "Not parsed yet";
    }

    function fareReason(row) {
      const stops = Number(row.stops) === 0 ? "nonstop" : `${row.stops} stop${Number(row.stops) === 1 ? "" : "s"}`;
      const baggage = row.baggage_included === "yes" ? "baggage included" : "baggage not included";
      return `Verified available round-trip fare within budget with ${stops} and ${baggage}; ranked by price, stops, and duration.`;
    }

    function renderRows(rows) {
      if (!rows || rows.length === 0) {
        return '<div class="empty-state">No exact fare match yet. The two-hour monitor will keep watching.</div>';
      }
      const body = rows.map((row) => `
        <tr>
          <td><strong>${escapeHtml(row.airline)}</strong></td>
          <td>${escapeHtml(row.case_depart)} to ${escapeHtml(row.case_return)}</td>
          <td>${escapeHtml(row.depart_airport)} ${formatTime(row.depart_datetime)} -> ${escapeHtml(row.arrive_airport)} ${formatTime(row.arrive_datetime)}</td>
          <td>${escapeHtml(row.arrive_airport)} ${formatTime(row.return_depart_datetime)} -> ${escapeHtml(row.depart_airport)} ${formatTime(row.return_arrive_datetime)}</td>
          <td>${escapeHtml(row.stops)}</td>
          <td class="price">$${Number(row.price_usd).toLocaleString()}</td>
          <td>${row.baggage_included === "yes" ? "Included" : "Not included"}</td>
          <td>${escapeHtml(fareReason(row))}</td>
        </tr>
      `).join("");
      return `
        <table>
          <thead>
            <tr>
              <th>Airline</th>
              <th>Dates</th>
              <th>Outbound</th>
              <th>Return</th>
              <th>Stops</th>
              <th>Price</th>
              <th>Baggage</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      `;
    }

    function renderApprovalNotice(data, rows) {
      if (!rows || rows.length === 0) return "";
      const emailTarget = data.traveler_email || "traveler's email id";
      return `
        <div class="approval-note">
          An email/SMS will be send to ${escapeHtml(emailTarget)} for approval before booking.
        </div>
      `;
    }

    function resetBookingControls() {
      bookingButton.classList.add("is-hidden");
      bookingButton.setAttribute("aria-hidden", "true");
      bookingStatus.textContent = "";
    }

    function showBookingSection() {
      resetBookingControls();
      bookingSection.classList.remove("is-hidden");
      bookingSection.setAttribute("aria-hidden", "false");
    }

    function hideBookingSection() {
      resetBookingControls();
      bookingSection.classList.add("is-hidden");
      bookingSection.setAttribute("aria-hidden", "true");
    }

    function resetMonitorResult() {
      output.innerHTML = emptyMonitorHtml;
      hideBookingSection();
    }

    acceptButton.addEventListener("click", () => {
      bookingButton.classList.remove("is-hidden");
      bookingButton.setAttribute("aria-hidden", "false");
      bookingStatus.textContent = "Accepted. Use Booking to continue the simulated approval flow.";
    });

    rejectButton.addEventListener("click", () => {
      resetMonitorResult();
    });

    bookingButton.addEventListener("click", () => {
      bookingStatus.textContent = "Booking request captured. Final booking remains pending traveler approval.";
    });

    function renderResult(data) {
      const monitor = data.monitor_result || {};
      const parsed = data.parsed || {};
      const rows = monitor.rows || [];
      output.innerHTML = `
        <div class="result-banner">
          <strong>${escapeHtml(monitor.status || "Request received")}</strong>
          <span>${escapeHtml(monitor.run_timing || "Immediate run completed; scheduled monitoring continues.")}</span>
        </div>
        <div class="summary-grid">
          <div class="metric"><span>Route</span><strong>${escapeHtml(parsed.origin)} -> ${escapeHtml(parsed.destination)}</strong></div>
          <div class="metric"><span>Dates</span><strong>${escapeHtml(formatDateRange(parsed.depart, parsed.return))}</strong></div>
          <div class="metric"><span>Budget</span><strong>$${Number(parsed.budget || 0).toLocaleString()}</strong></div>
          <div class="metric"><span>Next Step</span><strong>${escapeHtml(data.next_step?.schedule)} (${escapeHtml(data.next_step?.timezone)})</strong></div>
        </div>
        ${renderRows(rows)}
        ${renderApprovalNotice(data, rows)}
        <details>
          <summary>Raw agent response</summary>
          <pre class="json-details">${escapeHtml(JSON.stringify(data, null, 2))}</pre>
        </details>
      `;
      if (rows.length > 0) {
        showBookingSection();
      } else {
        hideBookingSection();
      }
    }

    async function submitPayload(url, payload) {
      hideBookingSection();
      output.innerHTML = '<div class="empty-state">Running immediate fare monitor...</div>';
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      renderResult(data);
    }

    chatSubmit.addEventListener("click", async () => {
      const request = chatRequest.value.trim();
      if (!request) {
        hideBookingSection();
        output.innerHTML = '<div class="empty-state">Add a conversational travel request first.</div>';
        return;
      }
      const formData = new FormData(form);
      try {
        await submitPayload("/api/traveler/chat", {
          request,
          traveler_email: formData.get("traveler_email") || null,
          recipient_email: formData.get("recipient_email") || null
        });
      } catch (error) {
        hideBookingSection();
        output.innerHTML = `<div class="empty-state">${escapeHtml(String(error))}</div>`;
      }
    });

    if (!SpeechRecognition) {
      voiceButton.disabled = true;
      voiceStatus.textContent = "Voice input is not available in this browser.";
    } else {
      recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.addEventListener("start", () => {
        voiceButton.classList.add("recording");
        voiceStatus.textContent = "Listening. Speak your travel request.";
      });

      recognition.addEventListener("result", (event) => {
        const transcript = Array.from(event.results)
          .map((result) => result[0].transcript)
          .join(" ");
        chatRequest.value = transcript;
      });

      recognition.addEventListener("end", () => {
        voiceButton.classList.remove("recording");
        voiceStatus.textContent = "Voice captured. Review or submit the chat request.";
      });

      recognition.addEventListener("error", (event) => {
        voiceButton.classList.remove("recording");
        voiceStatus.textContent = `Voice input stopped: ${event.error}`;
      });

      voiceButton.addEventListener("click", () => {
        recognition.start();
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {
        origin: formData.get("origin"),
        destination: formData.get("destination"),
        depart: formData.get("depart"),
        return_date: formData.get("return_date") || null,
        budget: formData.get("budget") ? Number(formData.get("budget")) : null,
        max_stops: formData.get("max_stops") ? Number(formData.get("max_stops")) : null,
        baggage_included: formData.get("baggage_included") === "on",
        flexibility: formData.get("flexibility") ? Number(formData.get("flexibility")) : null,
        traveler_email: formData.get("traveler_email") || null,
        recipient_email: formData.get("recipient_email") || null
      };

      try {
        await submitPayload("/api/traveler/request", payload);
      } catch (error) {
        hideBookingSection();
        output.innerHTML = `<div class="empty-state">${escapeHtml(String(error))}</div>`;
      }
    });
  </script>
</body>
</html>
"""


def _drop_generated_root_route() -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", set()) or set())
        )
    ]


def _agent_request_from_traveler(payload: TravelerRequestPayload) -> dict[str, Any]:
    return {
        "origin": payload.origin,
        "destination": payload.destination,
        "depart": payload.depart,
        "return": payload.return_date,
        "budget": payload.budget,
        "nonstop": payload.max_stops == 0,
        "flexibility": payload.flexibility,
    }


def _build_monitor_payload(
    *,
    trigger_response: dict[str, Any],
    max_stops: int | None,
    baggage_included: bool,
    traveler_email: str | None,
    recipient_email: str | None,
    source_mode: str,
) -> dict[str, Any]:
    parsed = trigger_response["parsed"]
    return {
        "monitor_id": "aus-to-cdg-synthetic-fare-monitor",
        "source": "travel-planner-agent",
        "source_mode": source_mode,
        "received_at": dt.datetime.now(dt.UTC).isoformat(),
        "criteria": {
            "origin": parsed.get("origin"),
            "destination": parsed.get("destination"),
            "depart": parsed.get("depart"),
            "return": parsed.get("return"),
            "budget": parsed.get("budget"),
            "nonstop": parsed.get("nonstop"),
            "flexibility": parsed.get("flexibility"),
            "max_stops": max_stops,
            "baggage_included": baggage_included,
        },
        "traveler_email": traveler_email,
        "recipient_email": recipient_email,
        "agent_response": trigger_response,
    }


def _infer_max_stops_from_chat(request: str, parsed: dict[str, Any]) -> int:
    text = request.lower()
    if parsed.get("nonstop") or re.search(r"\b(nonstop|non-stop|direct|no stop|nostop)\b", text):
        return 0
    numeric_match = re.search(r"\b(?:max(?:imum)?\s*)?(?:up to\s*)?(\d+)\s+stops?\b", text)
    if numeric_match:
        return int(numeric_match.group(1))
    word_match = re.search(r"\b(one|two)\s+stops?\b", text)
    if word_match:
        return {"one": 1, "two": 2}[word_match.group(1)]
    return 1


def _infer_baggage_from_chat(request: str) -> bool:
    return bool(re.search(r"\b(baggage|bag|checked bag|luggage)\b", request, re.IGNORECASE))


def _complete_submit_response(
    *,
    trigger_response: dict[str, Any],
    max_stops: int | None,
    baggage_included: bool,
    traveler_email: str | None,
    recipient_email: str | None,
    source_mode: str,
) -> dict[str, Any]:
    global latest_monitor_request

    response = dict(trigger_response)
    response["traveler_email"] = traveler_email
    response["preferences"] = {
        "max_stops": max_stops,
        "baggage_included": baggage_included,
    }
    response["intake_mode"] = source_mode
    monitor_payload = _build_monitor_payload(
        trigger_response=response,
        max_stops=max_stops,
        baggage_included=baggage_included,
        traveler_email=traveler_email,
        recipient_email=recipient_email,
        source_mode=source_mode,
    )
    immediate_monitor_result = _run_immediate_fare_monitor(monitor_payload)
    latest_monitor_request = monitor_payload
    latest_monitor_request["immediate_result"] = immediate_monitor_result
    response["next_step"] = {
        "monitor": monitor_payload["monitor_id"],
        "status": "sent",
        "immediate_run": "completed",
        "schedule": "Every 2 hours",
        "timezone": "America/Chicago",
        "handoff_url": "/api/monitor/latest-request",
    }
    response["monitor_result"] = immediate_monitor_result
    return response


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _format_time(value: str | None) -> str:
    if not value:
        return ""
    parsed = dt.datetime.fromisoformat(value)
    return parsed.strftime("%H:%M")


def _fare_reason(row: dict[str, Any]) -> str:
    stops = "nonstop" if int(row["stops"]) == 0 else f"{row['stops']} stop"
    if int(row["stops"]) > 1:
        stops += "s"
    baggage = "baggage included" if row["baggage_included"] == "yes" else "baggage not included"
    return (
        "Verified available round-trip fare within budget with "
        f"{stops} and {baggage}; ranked by price, stops, and duration."
    )


def _fare_table_markdown(rows: list[dict[str, Any]]) -> str:
    header = (
        "| Airline | Dates | Outbound | Return | Stops | Price | Baggage | Reason |\n"
        "|---|---|---|---|---:|---:|---|---|"
    )
    body = [
        (
            f"| {row['airline']} | {row['case_depart']} to {row['case_return']} | "
            f"{row['depart_airport']} {_format_time(row['depart_datetime'])} -> "
            f"{row['arrive_airport']} {_format_time(row['arrive_datetime'])} | "
            f"{row['arrive_airport']} {_format_time(row['return_depart_datetime'])} -> "
            f"{row['depart_airport']} {_format_time(row['return_arrive_datetime'])} | "
            f"{row['stops']} | ${int(row['price_usd']):,} | "
            f"{'Included' if row['baggage_included'] == 'yes' else 'Not included'} | "
            f"{_fare_reason(row)} |"
        )
        for row in rows
    ]
    return "\n".join([header, *body])


def _run_immediate_fare_monitor(monitor_payload: dict[str, Any]) -> dict[str, Any]:
    """Run the same synthetic fare filters immediately for the submitted request."""
    criteria = monitor_payload["criteria"]
    cases = {row["case_id"]: row for row in _read_csv(DATA_DIR / "monitoring_cases.csv")}

    rejected_or_duplicate: set[str] = set()
    for row in _read_csv(DATA_DIR / "alert_history.csv"):
        flight_ids = [flight_id.strip() for flight_id in row["flight_ids"].split(";")]
        if row["human_response"] == "rejected" or row["status"] == "sent":
            rejected_or_duplicate.update(flight_id for flight_id in flight_ids if flight_id)

    candidates = []
    for row in _read_csv(DATA_DIR / "flight_snapshots.csv"):
        case = cases.get(row["case_id"], {})
        if row["depart_airport"] != criteria["origin"]:
            continue
        if row["arrive_airport"] != criteria["destination"]:
            continue
        if case.get("depart_date") != criteria["depart"]:
            continue
        if case.get("return_date") != criteria["return"]:
            continue
        if row["availability_status"] != "available" or row["data_quality"] != "verified":
            continue
        if int(row["stops"]) > int(criteria["max_stops"]):
            continue
        if criteria["baggage_included"] and row["baggage_included"] != "yes":
            continue
        if criteria["budget"] is not None and int(row["price_usd"]) > int(criteria["budget"]):
            continue
        if row["flight_id"] in rejected_or_duplicate:
            continue
        candidates.append(
            {
                **row,
                "case_depart": case.get("depart_date"),
                "case_return": case.get("return_date"),
            }
        )

    rows = sorted(
        candidates,
        key=lambda row: (
            int(row["price_usd"]),
            int(row["stops"]),
            int(row["duration_minutes"]),
        ),
    )[:2]

    status = "STOP CONDITION MET" if rows else "NO MATCH YET"
    return {
        "status": status,
        "run_timing": "Immediate once on form submit; scheduled monitor continues every 2 hours.",
        "schedule": "Every 2 hours",
        "timezone": "America/Chicago",
        "rows": rows,
        "codex_table_markdown": _fare_table_markdown(rows) if rows else "",
        "note": (
            "Booking is simulated; human approval is required before any simulated booking action."
        ),
    }


_drop_generated_root_route()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def traveler_home() -> HTMLResponse:
    return HTMLResponse(_traveler_form_html())


@app.get("/traveler", response_class=HTMLResponse, include_in_schema=False)
def traveler_form() -> HTMLResponse:
    return HTMLResponse(_traveler_form_html())


@app.post("/api/traveler/request")
def submit_traveler_request(payload: TravelerRequestPayload) -> dict[str, Any]:
    agent_payload = _agent_request_from_traveler(payload)
    trigger_response = trigger_travel_planner(
        TravelTriggerRequest(
            request=json.dumps(agent_payload),
            recipient=payload.recipient_email,
            dry_run=True,
        )
    )
    return _complete_submit_response(
        trigger_response=trigger_response.model_dump(),
        max_stops=payload.max_stops,
        baggage_included=payload.baggage_included,
        traveler_email=payload.traveler_email,
        recipient_email=payload.recipient_email,
        source_mode="manual",
    )


@app.post("/api/traveler/chat")
def submit_traveler_chat(payload: TravelerChatPayload) -> dict[str, Any]:
    trigger_response = trigger_travel_planner(
        TravelTriggerRequest(
            request=payload.request,
            recipient=payload.recipient_email,
            dry_run=True,
        )
    )
    response = trigger_response.model_dump()
    return _complete_submit_response(
        trigger_response=response,
        max_stops=_infer_max_stops_from_chat(payload.request, response["parsed"]),
        baggage_included=_infer_baggage_from_chat(payload.request),
        traveler_email=payload.traveler_email,
        recipient_email=payload.recipient_email,
        source_mode="chat",
    )


@app.get("/api/monitor/latest-request")
def get_latest_monitor_request() -> dict[str, Any]:
    if latest_monitor_request is None:
        return {
            "monitor_id": "aus-to-cdg-synthetic-fare-monitor",
            "source": "travel-planner-agent",
            "status": "empty",
            "message": "No traveler request has been submitted yet.",
        }
    return {"status": "ready", **latest_monitor_request}


@app.post("/api/triggers/travel-intake")
def trigger_travel_intake(payload: TravelTriggerRequest) -> dict[str, Any]:
    """Deterministic scheduler-callable travel intake trigger."""
    return trigger_travel_planner(payload).model_dump()


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
