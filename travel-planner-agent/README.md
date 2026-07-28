# travel-planner-agent

Prototype travel intake agent that converts an initial trip request into strict JSON.
Agent generated with `agents-cli` version `1.2.1`

## Project Structure

```
travel-planner-agent/
├── app/         # Core agent code
│   ├── agent.py               # Main agent logic
│   ├── fast_api_app.py        # FastAPI Backend server
│   └── app_utils/             # App utilities and helpers
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Antigravity CLI](https://antigravity.google/) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

Expose the local ADK web UI through the FastAPI app:

```bash
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000
```

Then open `http://127.0.0.1:8000`.

## Example

Input:

```text
I need to travel from Dallas to London.
Depart July 10
Return July 18
Budget under $900
Prefer nonstop
Window +/-2 days
```

Output:

```json
{"origin":"DFW","destination":"LHR","depart":"2027-07-10","return":"2027-07-18","budget":900,"nonstop":true,"flexibility":2}
```

## Scheduler Trigger

Schedulers can call the deterministic backend trigger without invoking the LLM:

```bash
curl -X POST http://127.0.0.1:8000/api/triggers/travel-intake \
  -H 'Content-Type: application/json' \
  -d '{
    "request": "I need to travel from Dallas to London. Depart July 10 Return July 18 Budget under $900 Prefer nonstop Window +/-2 days",
    "recipient": "preview@example.com",
    "dry_run": true
  }'
```

Dry runs return an email preview with `"sent": false` and never send email.

Shared Codex credentials are loaded only at runtime from
`CODEX_SHARED_CREDENTIALS_PATH` or `CODEX_CREDENTIALS_PATH`. Keep that file
outside the repo.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        || [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.
