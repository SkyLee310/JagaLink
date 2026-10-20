# JagaLink — Community Early-Warning Safety Network

JagaLink links a guarded community's isolated CCTV cameras and sensors into one spatial graph, so anonymous movement paths alert the nearest guard early, name the next camera to check, and can be traced after an incident — all without facial recognition. It is a web prototype for the Sime Darby Property University Hackathon 2026: Must features F1–F8 ship by 23 Oct 2026; Should features F9–F13 wait for the 11 Nov final.

## Read the docs first

Before starting any feature, read every file in `docs/`. The docs define the product; the code follows them.

| File | Holds |
|---|---|
| `docs/DECISIONS.md` | Locked rules (D-01 …), each ✅ decided or ⏳ open |
| `docs/PRD.md` | Product behaviour, features F1–F13, acceptance criteria |
| `docs/TECH_SPEC.md` | Architecture, data model, API, milestones M0–M10 |
| `docs/TASKS.md` | Milestone tasks, owners, files currently being edited |
| `docs/PROGRESS.md` | Session log; its ⚠️ entries are known traps |
| `docs/PROBLEM_STATEMENT.md` | Background and evidence only |

When docs conflict, DECISIONS wins, then PRD for product behaviour and TECH_SPEC for technical choices; PROBLEM_STATEMENT is background only (its 3D layout is superseded by PRD W8: 2D). Bring any other conflict to the user before coding.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend (`frontend/`, Vercel) | React 19, TypeScript, Vite, Tailwind, TanStack Query, Zustand, react-konva |
| Backend (`backend/`, Google Cloud Run) | Python 3.12, FastAPI, Pydantic v2, uvicorn, networkx |
| Database (Neon) | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Realtime | Server-Sent Events via a fetch-based client that sends the bearer token |
| Agent (F7) | Google Vertex AI (Gemini, model per PRD Q6), google-genai SDK, function calling, JSON-schema output |
| Should phase only | F10: Ultralytics YOLO, ByteTrack, OpenCV, ffmpeg · F13: pandas, scikit-learn |
| Tests | pytest, Vitest, Playwright |
| Tooling | uv, pnpm, Docker Compose, GNU make, GitHub Actions, ruff, oxlint |
| Supporting (D-78) | Backend: psycopg[binary], pydantic-settings, httpx, tzdata · Frontend: konva, @tailwindcss/vite, openapi-typescript, react-router, jsdom, @testing-library/react, @testing-library/dom, @playwright/test, plus the Vite React-TS template's dev dependencies |

## Commands

Run from the repo root once M0 lands. The `Makefile` is the source of truth; each target wraps a plain `uv run …` or `pnpm …` call.

| Command | Does |
|---|---|
| `make dev` | Postgres in Docker, backend and frontend with reload |
| `make seed` | Migrate, then load the seeded community, users and scenarios |
| `make test` | pytest (unit + golden scenarios) and Vitest |
| `make lint` | ruff check, ruff format --check, oxlint, tsc --noEmit |
| `make build` | Frontend production build and backend Docker image |
| `make eval` | Replay every scenario headless and print the F8 report |
| `make types` | Regenerate frontend API types from the backend's `openapi.json` |
| `make demo` | Playwright run of the demo script |

Prerequisites: Docker, uv, Node with pnpm, GNU make (Windows: `winget install ezwinports.make`).

## Coding conventions

- **One event contract.** Simulator, video detector and eval runner post the same event JSON to ingest; F3–F7 read only from the event stream.
- **Event time.** The pipeline runs on each event's `ts` through the simulated clock (`engine/clock.py`), so a scenario gives identical results on every run.
- **Pure engine.** `backend/app/engine/` is pure functions, data in and data out; DB, network and clock access stay in `routers/`, `sim/` and `db/`.
- **Tools-only agent.** The agent reads data only through `get_neighbors`, `get_track`, `get_events`, `get_guards` and `get_alert`; every Vertex AI call has a timeout and a rule-based fallback; every timeline entry cites real event IDs or says "cannot be determined".
- **Privacy by construction.** Store event metadata and expiring anonymous IDs only; outputs describe behaviour, never identity or intent.
- **Migrations.** Every schema change is an Alembic migration; tables use UUID keys, `community_id` where it applies, and `timestamptz`.
- **API shape.** REST under `/api/v1`; ISO-8601 timestamps with milliseconds; errors as `{code, message, details}` (409 duplicate link, 422 self-link or malformed event); role checks on the server.
- **Generated types.** Frontend API types come from `make types`; rerun it after every API change and commit `backend/openapi.json` with the regenerated types (CI fails when either is stale).
- **Feature folders.** Frontend code lives in `frontend/src/features/<feature>/`; the API base URL comes from `VITE_API_URL`.
- **Server-side secrets.** Google credentials stay on the server: the deployed API runs as its Cloud Run service account, and local runs use `gcloud auth application-default login`. Other secrets live in `.env` and Secret Manager; commit `.env.example` with placeholders.
- **Tests.** Engine functions get pytest unit tests; each scenario has golden expected paths, alerts and timeline entries in `backend/data/scenarios/`. Change a golden file only for an intended behaviour change, and say so in the commit.
- **Traceable commits.** Prefix the type and the feature or milestone ID: `feat(F3): join tracks inside the walking window`.

## Workflow

- Work one milestone (vertical slice) from `docs/TASKS.md` at a time; present the plan and wait for approval before writing code.
- A task is done when `make lint`, `make test` and `make build` pass and its PRD acceptance criteria hold.
- Close out by marking the task ✅ with the date in `docs/TASKS.md` and appending to `docs/PROGRESS.md`: what changed, implementation decisions, ⚠️ traps for the next session.

## Don't

Hard guardrails. When one blocks you, stop and ask the user.

- **Don't add dependencies on your own.** Use what the stack table lists; anything new needs the user's OK first, then a row in that table.
- **Don't touch files outside the task.** Edit only what the current task needs; log anything else you notice in `docs/PROGRESS.md`.
- **Don't change product behaviour fixed in `docs/`.** Propose the change to the user; the code follows the docs as written until they are updated.
