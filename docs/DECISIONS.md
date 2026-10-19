# DECISIONS.md — Locked decisions

Settled rules for JagaLink. Agents follow every ✅ entry and change none on their own: a change goes to the user first, then into this file (status, reasoning, Changelog line), then into PRD/TECH_SPEC if they are affected, and only then into code (PROMPTS.md §9). A ⏳ entry is open: it carries a recommendation, and work that depends on it waits until the user marks it ✅.

Sources: PRD = `docs/PRD.md`, TS = `docs/TECH_SPEC.md`, PS = `docs/PROBLEM_STATEMENT.md`.

## Decided

### Scope and schedule

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-01 | Must features F1–F8 ship in the proposal submission, due 23 Oct 2026 23:59. Should features F9–F13 are built only after a Top 10 result (28 Oct), for the final submission on 11 Nov. | Fixed hackathon gates · PRD §1, §4 | ✅ |
| D-02 | The 23 Oct submission is a pitch deck of at most 10 pages, a 5-minute demo video or demo link, and a prototype or code link. | Hackathon rules · PRD §1 | ✅ |
| D-03 | The demo is a screen recording from the deployed app, made after code freeze; there is no live demo. | A recording is sufficient · PRD §7, TS §8 M6 | ✅ |
| D-04 | Out of scope: real CCTV or VMS connection (W4), automatic police reports or dispatch (W5), a native mobile app — web only (W6), multi-township deployment (W7), a 3D layout view (W8). | PRD §4 Won't | ✅ |
| D-05 | One simulated community; every table it applies to carries `community_id`, so a second community needs no schema change. | Scalable is argued in the pitch only · TS §1, PRD W7 | ✅ |
| D-06 | Inputs are scripted simulation and licensed public video only; no footage from a real community. | No real system or permission · PRD §6, TS §1 | ✅ |
| D-07 | Code freezes once M5 is done; only fixes after that. If time runs short, cut M4 map-highlight polish, then the M4 thresholds screen, then the M3 expiry screen. The golden scenario tests and the evaluation report are never cut. | They are the evidence judges score · TS §8 | ✅ |
| D-08 | The product is called JagaLink. This repo's root stands in for TECH_SPEC's `early-warning/`: `frontend/`, `backend/` and `docs/` sit at the top level. | Approved with AGENTS.md, 16 Oct | ✅ |
| D-69 | Scenario parameters (PRD Q2) come from a fictional landed township drawn as our own plan — one gated entrance, about 6 lanes, 20 nodes — with walking times from lane lengths at 1.2–1.4 m/s. The layout is checked against a real layout or a credited OpenStreetMap trace by 21 Oct. | No real layout is available yet · accepted 16 Oct | ✅ |

### Privacy and ethics

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-09 | No facial or identity recognition (W1), no suspect labelling or intent prediction (W2), no licence-plate recognition (W3). | Privacy risk; cross-camera re-identification is unsolved · PRD §4, §6, PS §2 | ✅ |
| D-10 | Nothing stores image bytes, face features, plates or names of members of the public; event `attrs` hold no personal data. No real face appears in the demo, deck or docs — any public-video frame shown is blurred or cropped. | Privacy by construction · TS §3–4, §9, PRD §5 | ✅ |
| D-11 | Objects carry anonymous IDs that expire; a purge job deletes expired tracks, and an expired ID can no longer be queried. | PRD F3, TS §3 | ✅ |
| D-12 | Data handling follows PDPA notice, purpose, security and deletion principles; retention is short and configurable (the period is PRD Q3). | CCTV showing identifiable people is personal data · PS §8, PRD §5 | ✅ |
| D-13 | Human in the loop: the system only suggests; guards and supervisors decide every response. | PRD §5, §6 | ✅ |

### Product behaviour

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-14 | F1 — 2D layout editor (react-konva over an optional background image): add, move and delete cameras and sensors, set heading, link two nodes with min and max walking times. Self-links and duplicate links are rejected; a saved layout reloads identically. | 2D is enough · PRD F1, W8 | ✅ |
| D-15 | F2 — Two scripted scenarios replace detection. S1: an unfamiliar vehicle repeatedly in residential lanes in the early evening. S2: a person moving along a camera chain toward houses at night. Start, pause and reset are one action each; repeated runs give the same event sequence. | PRD F2 | ✅ |
| D-16 | F2 — An event holds `ts`, `node_id`, `type` (appear, disappear, dwell), `object_class` (person, vehicle), a per-camera `local_track_id`, `attrs` and `source` (sim, video) — nothing that identifies a person. | One contract for every source · PRD F2, TS §4–5 | ✅ |
| D-17 | F3 — A track that leaves camera A joins an appearance at linked camera B only within [exit + `travel_min_s`, exit + `travel_max_s`]; anything else starts a new track. Only object class and timing count; the best time fit wins when objects compete. | PRD F3, TS §3 | ✅ |
| D-18 | F4 — Three human-defined rules: after-hours entry, loitering beyond a threshold in one zone, off-route movement. Thresholds live in `rule_config` and change without code; every anomaly and alert carries its rule and the event IDs it relied on. | Explainability · PRD F4, §5 | ✅ |
| D-19 | F5 — The alert goes to the on-duty guard with the shortest walking time to the event node (Dijkstra on the camera graph); with no guard on duty it escalates to the supervisor. | PRD F5, TS §3 | ✅ |
| D-20 | F5 — The system names one most likely next camera with its basis (walking time, distance, known path). | PRD F5 | ✅ |
| D-21 | F6 — A new alert reaches the screen within 2 s of its event entering the stream, with a notification cue. Its card shows location, rule, severity, next camera and a map highlight; confirm or dismiss is one click with an optional one-line reason, recorded in the incident timeline; 5 simultaneous alerts fit without scrolling. | PRD F6, §5 | ✅ |
| D-22 | F7 — For each alert the agent returns a severity (high, medium, low) and a reason of at most three sentences; after each scenario it writes a time-ordered incident timeline. | PRD F7 | ✅ |
| D-23 | F7 — Every timeline `fact` entry cites at least one event that exists in the stream; an uncited entry is dropped or rewritten as an explicit `unknown` ("cannot be determined") entry. | No invented detail · PRD F7, TS §3 | ✅ |
| D-24 | F7 — Agent output makes no suspect judgement and no inference about identity or intent. | PRD F7, W2 | ✅ |
| D-25 | F8 — One command runs every scenario and prints one report: time to first alert, next-camera accuracy, false alerts per camera per night and timeline match, each next to a guards-check-screens-in-turn baseline on the same scenarios. | PRD F8 | ✅ |
| D-26 | F8 — The baseline models a guard cycling through N screens with a fixed dwell per screen; time to alert is the wait until the guard's screen shows the event's camera. N and dwell sit in config (values: D-68). | TS §3 | ✅ |
| D-27 | Every scenario runs cleanly end to end from a fresh start, and every scenario and evaluation result reproduces from the same version. | Demo stability, reproducibility · PRD §5 | ✅ |
| D-28 | No real login: users pick a seeded name and role (guard or supervisor). The pitch states plainly that auth is out of scope. | TS §1, §9 | ✅ |
| D-29 | Should features follow PRD §5 F9–F13; the F13 baseline uses only public video and simulated data, and supervisors can always override a learned threshold. | PRD §4–5 | ✅ |
| D-66 | Screens per role: a guard gets the alert console (alerts, map, timeline); a supervisor gets the console plus the layout editor, scenario player, rules and eval pages. | Routing and server role checks need it · accepted 16 Oct | ✅ |

### Architecture

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-30 | One event contract: the simulator, video detector and eval runner all post the same event JSON to `POST /events`; F3–F7 read only from the event stream. | TS §3 | ✅ |
| D-31 | The pipeline runs on event time (`ts`) through a simulated clock, never wall time. | Same alerts on every run · TS §3 | ✅ |
| D-32 | Path linker, rule engine, router and next-camera scoring are pure functions in `backend/app/engine/` with no I/O. | Unit-testable; `make eval` needs no server · TS §3 | ✅ |
| D-33 | The agent reaches data only through `get_neighbors`, `get_track`, `get_events`, `get_guards` and `get_alert`; it never sees pixels or raw video. | PRD F7, TS §3 | ✅ |
| D-34 | Every Vertex AI call has a timeout and a rule-based fallback, so a slow or failed call never blocks an alert. | TS §6, §9 | ✅ |
| D-35 | The eval runner replays scenarios through the same engine as the demo. | Demo and numbers cannot drift apart · TS §3 | ✅ |
| D-36 | Live updates use Server-Sent Events on `GET /stream?run_id=` with message types `event`, `track_update`, `alert`, `alert_update`, `timeline_ready`; the browser uses a fetch-based SSE client so it can send the bearer token. | One-way push fits the 2-s target · TS §2, §5 | ✅ |

### Data and API

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-37 | The schema follows TS §4: 17 core tables plus `audit_log` and `retention_policy` for F12; UUID primary keys, `community_id` where it applies, `timestamptz` times. | TS §4 | ✅ |
| D-38 | Every schema change is an Alembic migration, from day one. | TS §2 | ✅ |
| D-39 | `link` is unique on (`from_node_id`, `to_node_id`) and checks that from ≠ to. | Backs F1's rejections · TS §4 | ✅ |
| D-40 | REST + JSON under `/api/v1`: UUID IDs, ISO-8601 timestamps with milliseconds, errors as `{code, message, details}` — 409 for a duplicate link, 422 for a self-link or a malformed event. | TS §5 | ✅ |
| D-41 | `POST /session` returns a bearer token for the `Authorization` header; role checks run on the server; CORS allows only the frontend origin. | TS §5 | ✅ |
| D-42 | The backend publishes `openapi.json`, committed as `backend/openapi.json`; frontend API types are generated from it (`make types`), and CI fails when either is stale. | Types cannot drift from the API · TS §7; the staleness check came with the M0 plan, 16 Oct | ✅ |
| D-75 | Primary keys stay UUIDs; `zone`, `node` and `app_user` also carry a human-readable `code` (e.g. `z-gate`, `c-gate-02`, `u-guard-02`), unique per community. Scenario files, golden files and layout exports reference codes. | Stable references across databases · accepted 16 Oct; `zone` added with the M0 plan | ✅ |
| D-76 | `POST /session` returns an HMAC-signed token built with Python's standard library — user ID, role and a 12 h expiry, keyed by `SESSION_SECRET`. There is no session table and no JWT package. | No new dependency or table · accepted 16 Oct | ✅ |

### Stack, tooling and hosting

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-43 | Frontend: React 19, TypeScript, Vite, Tailwind, TanStack Query, Zustand, react-konva. Backend: Python 3.12, FastAPI, Pydantic v2, uvicorn, networkx. Database: PostgreSQL 16, SQLAlchemy 2, Alembic. Tests: pytest, Vitest, Playwright. | One backend language for API, simulator, rules, eval and agent · TS §2; React 19 since 16 Oct, because current react-konva and react-router need it | ✅ |
| D-44 | The agent runs on Google Vertex AI (Gemini family) through the google-genai SDK, with function calling and JSON-schema output. The exact model is D-79. | Platform decision · PRD §7, TS §2 | ✅ |
| D-45 | Should-phase libraries: Ultralytics YOLO, ByteTrack, OpenCV, ffmpeg for F10 (offline; YOLO is AGPL-3.0, fine for the competition only); pandas and scikit-learn for F13. | TS §2, §6 | ✅ |
| D-46 | Tooling: uv, pnpm, Docker Compose, GNU make, GitHub Actions; ruff for Python, oxlint and `tsc` for TypeScript. | TS §2; linters added with AGENTS.md, 16 Oct; oxlint replaced ESLint the same day because the Vite template now ships it | ✅ |
| D-47 | Hosting: `frontend/` on Vercel; `backend/` on Google Cloud Run in `asia-southeast1`, at most one instance; PostgreSQL 16 on Neon's free plan in AWS Singapore. The API reaches Vertex AI as its Cloud Run service account, so no service-account key is stored. | Two independent deploys · TS §2, §6, §7; on 19 Oct Cloud Run and Neon replaced Railway after a paid Railway plan did not work out, reusing the Google Cloud billing that Vertex AI needs anyway | ✅ |
| D-48 | CI: GitHub Actions `frontend.yml` and `backend.yml` run on every pull request and push to `main`; each skips its test job unless its folder changed (`frontend.yml` also runs when `backend/openapi.json` changes). CI runs the golden scenario tests, and failing tests block merges through branch protection on `main`. | TS §2, §7, §9; on 16 Oct the path check moved from the trigger into the job, because GitHub leaves a skipped workflow's required check pending | ✅ |
| D-49 | Commit messages start with a type and the feature or milestone ID, e.g. `feat(F3): join tracks inside the walking window`. | Traceability · AGENTS.md, 16 Oct | ✅ |
| D-78 | Approved supporting packages. Backend: `psycopg[binary]`, `pydantic-settings`, `httpx`. Frontend: `konva`, `@tailwindcss/vite`, `openapi-typescript`, `react-router`, `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@playwright/test`, plus the Vite React-TS template's own dev dependencies. SSE is hand-written on both sides. | Implied by the stack; listed in AGENTS.md · accepted 16 Oct; `@testing-library/dom` added with the M0 plan, as a required peer of `@testing-library/react` | ✅ |
| D-81 | The code lives in a public GitHub repo named `JagaLink`, so judges can open the code link. | The submission needs a code link · accepted 16 Oct | ✅ |

### Testing and process

| ID | Decision | Reason · source | Status |
|---|---|---|---|
| D-50 | Tests: pytest unit tests on pure logic; golden scenario tests (expected paths, alerts and timeline entries; a change that alters them fails CI); API tests against a test database; Playwright end to end following the demo script, with a ≤2 s latency assertion. | TS §9 | ✅ |
| D-51 | Milestones M0–M10 are vertical slices; a slice is done only when it is merged, deployed, and its demo-script step works in the browser. | TS §8 | ✅ |

## Open — needs the user

Each row carries a recommendation. "Needed by" is the first milestone that depends on it.

### Product behaviour

| ID | Question → recommendation | Why it matters | Needed by | Status |
|---|---|---|---|---|
| D-52 | Which rule catches S1? Its vehicle passes through the lanes again and again in the early evening, before any quiet hours, and never stops. → Measure loitering as a track's cumulative time in one zone within a rolling window (default ≥180 s within 10 min), so repeat passes add up. | Otherwise S1 raises no alert | M2 | ⏳ |
| D-53 | Off-route can't fire as written: the linker only joins along links, so a track never contains "a transition with no link". → Seed normal routes (node-code sequences) with the community layout; off-route = a transition that no normal route contains. F13 later adds learned rare transitions. Needs a new jsonb field on `community`. | Contradiction between TS §3's rule and its linker; schema addition | M2 | ⏳ |
| D-54 | After-hours window and time zone. → Store all times in UTC; evaluate rules in `community.timezone` (Asia/Kuala_Lumpur); scenario scripts use local time; quiet period 23:00–06:00, applied to residential lane zones only. (TS §5's example `21:14Z` is 05:14 in Malaysia.) | A wrong zone shifts every after-hours result | M2 | ⏳ |
| D-55 | Link times are walking times, so a car arrives "too early" and splits into new tracks. → A per-class factor in linker config scales `travel_min_s`: person 1.0, vehicle 0.3. | S1 is a vehicle | M3 | ⏳ |
| D-56 | Track lifecycle and expiry. → A track closes when no linked appearance arrives within the largest outgoing `travel_max_s`. TTL defaults to 24 h after `last_ts` (config; the demo can shorten it). Expiry deletes the track and its segments and clears `anomaly.track_id`; alerts keep their evidence event IDs and timeline. | F3 expiry without losing incident records | M3 | ⏳ |
| D-57 | Next-camera inputs. → Score neighbours by direction of travel (from node coordinates), no immediate backtrack, walking time, and the transition's share of normal routes (D-53); weights in config. The score never reads `scenario.truth_path`. | TS §3 scores by "the scenario's known routes"; reading the truth path would fake F8's accuracy | M4 | ⏳ |
| D-58 | Guard positions and route weight. → Each guard's `current_node_id` and `on_duty` come from the scenario's roster and stay fixed during a run; Dijkstra weight = (`travel_min_s` + `travel_max_s`) / 2. | F5 routing needs both | M4 | ⏳ |
| D-59 | Alert de-duplication. → One open alert per (track, rule); repeat matches add evidence and send `alert_update`, not a new card. | Keeps false-alert counts honest and cards within 5 | M4 | ⏳ |
| D-60 | Rule-based severity, used before M5 and whenever the agent fails. → off_route = high; after_hours = medium; loiter = medium; two or more rules on one track = high. Mapping in config. | The M4 card needs a severity | M4 | ⏳ |
| D-61 | A Gemini round trip may not fit the 2-s budget. → Push the alert as soon as the router finishes, with the rule-based severity marked provisional; triage runs in the background and sends `alert_update` (timeout 8 s, after which the fallback stays). This changes TS §3, where the alert waits for the agent. | 2-s target vs agent latency | M5 | ⏳ |
| D-62 | What is an incident? → One alert. Its timeline (`timeline_entry.alert_id`) is generated when the run ends (`timeline_ready`) and on demand, and includes the guard's confirm or dismiss. | PRD says "after each scenario"; TS keys timelines by alert | M5 | ⏳ |
| D-63 | Sensors. → Placed and linked like cameras; they emit the same event types with a scripted object class; no sensor-specific logic in Phase 1. | F1 includes sensors; nothing defines their events | M1 | ⏳ |
| D-64 | Zones in the editor. → Zones (street, gate, lane) are seeded and shown read-only; each node's zone is set in the editor's properties panel; drawing polygons stays out of Phase 1. | Rules need zones; F1 doesn't mention editing them | M1 | ⏳ |
| D-65 | Duplicate links across directions. → (A, B) and (B, A) are the same link when either is bidirectional; two one-way links in opposite directions are allowed. | F1 duplicate rule | M1 | ⏳ |
| D-67 | Screen size for the "5 alerts without scrolling" check. → A 1366×768 laptop (guardhouse PC); on a phone the console works with scrolling. | The F6 criterion needs a viewport | M4 | ⏳ |

### Evaluation

| ID | Question → recommendation | Why it matters | Needed by | Status |
|---|---|---|---|---|
| D-68 | Targets and baseline values (PRD Q1). → Adopt the PRD's suggested targets: next camera ≥80%, ≤2 false alerts per camera per night, timeline match ≥90%, time to alert below baseline. Baseline: one guard cycles through every camera feed one at a time, 10 s each. | Report thresholds; PRD due 21 Oct | M6 | ⏳ |
| D-70 | Where ground truth lives. → Only in the scenario file (target vs background labels, true path, expected alerts and timeline); the player never posts it, so F3–F7 cannot see it. | Keeps the metrics honest | M2 | ⏳ |
| D-71 | Normal traffic. → Every scenario mixes its target with seeded, deterministic background movement along normal routes across a full 18:00–06:00 night; `make eval` replays the whole night headless, and the live demo plays a window around the target. | False alerts are unmeasurable without it | M2 | ⏳ |
| D-72 | What "per night" means. → False alerts per camera per night = alerts caused only by background objects ÷ number of cameras, over the full simulated night. | Metric definition | M6 | ⏳ |
| D-73 | Timeline match. → The scenario file lists expected timeline entries (event references, in order); an entry matches when an agent `fact` entry cites the same events in the same order with a time within ±1 s; score = matched ÷ expected. | Metric definition | M6 | ⏳ |
| D-74 | LLM output varies run to run. → CI golden tests use the rule-based agent; `make eval` and the demo replay agent responses recorded once from Vertex AI per scenario; `AGENT=live` calls Vertex AI. | Reproducible numbers (D-27) | M5 | ⏳ |

### Data, API and stack

| ID | Question → recommendation | Why it matters | Needed by | Status |
|---|---|---|---|---|
| D-77 | Process model. → One backend instance: the scenario player is an in-process asyncio task, SSE fan-out is in memory, one live run per community at a time; no Redis or queue. | Simplest setup that meets the 2-s target | M2 | ⏳ |
| D-79 | Gemini model and region (PRD Q6). → The current Flash-tier Gemini model in `asia-southeast1`, confirmed by a quick latency and cost check. | F7 cost and latency | M5 | ⏳ |
| D-80 | Google Cloud setup. → A GCP project on the user's billing account, which also hosts Cloud Run (D-47), with Vertex AI enabled and a service account holding the Vertex AI User role. The deployed API runs as that service account, so production needs no key; local runs use `gcloud auth application-default login`, and no key goes into git. | M5 is blocked without it | M5 | ⏳ |

PRD §7 questions Q3 (retention period), Q4 (public video licences), Q5 (learning normal movement), Q7 (supervisor interview) and Q8 (pitch format) stay open in the PRD for Phase 2; Q1, Q2 and Q6 are D-68, D-69 and D-79 here.

## Changelog

| Date | Change |
|---|---|
| 2026-10-16 | Created from PRD and TECH_SPEC: D-01–D-51 decided, D-52–D-81 open. |
| 2026-10-16 | D-66, D-69, D-75, D-76, D-78, D-81 decided: the user accepted the recommendations, unblocking M0. |
| 2026-10-16 | M0 plan approved: D-42 (commit `backend/openapi.json`; CI fails on stale types), D-43 (React 19), D-46 (oxlint instead of ESLint), D-48 (path check moves from the trigger into the job), D-75 (`code` on zone too), D-78 (adds `@testing-library/dom`). |
| 2026-10-19 | D-47 changed: the backend moves from Railway to Google Cloud Run and PostgreSQL to Neon's free plan, both in Singapore, after a paid Railway plan did not work out. D-80's recommendation drops the stored key, since the API runs as its Cloud Run service account. |
