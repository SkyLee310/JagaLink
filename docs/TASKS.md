# TASKS.md — Milestones and tasks

Each milestone is a vertical slice: when it ends, something new works in the deployed app, from screen to database. It is done when it is merged, deployed, its demo step works in the browser, and `docs/PROGRESS.md` is updated (D-51). **Needs** lists the ⏳ entries in `docs/DECISIONS.md` that must be ✅ before the milestone starts. Target dates are suggestions.

Status: ⬜ todo · 🔄 in progress · ✅ done (date) · ⛔ blocked. Owner: a name or agent handle (`@sky`, `@agent-a`, `@agent-b`). "(human)" marks work only a person can do.

## Files currently being edited

Add a row before you start editing; remove it when you finish.

| Owner | Task | Files | Since |
|---|---|---|---|
| @agent-a | M3 | `backend/app/{engine,sim,db,routers,schemas,core}/`, `backend/app/db/migrations/versions/`, `backend/data/scenarios/golden/`, `backend/tests/`, `frontend/src/{api,lib,components/map,features/scenario-player}/` | 2026-10-20 |

## Phase 1 — proposal submission, 23 Oct

### M0 · Walking skeleton — target Sat 17 Oct

Slice: open the deployed URL, pick Guard or Supervisor, see the seeded community map from the database.
Needs: D-66, D-69, D-75, D-76, D-78, D-81.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M0.1 | Dev setup: install GNU make and pnpm on this machine (with the user's OK); `git init`, `.gitignore`; create the GitHub repo (D-81) and push. | `make --version` and `pnpm --version` work; `main` is on GitHub. | @agent-a | ✅ 2026-10-17 |
| M0.2 | Backend scaffold: uv project on Python 3.12; FastAPI under `/api/v1` with a health route; settings from env; CORS for `FRONTEND_ORIGIN`; `{code, message, details}` errors; `.env.example`. | `GET /api/v1/health` returns 200; `ruff check` and `pytest` pass. | @agent-a | ✅ 2026-10-17 |
| M0.3 | Database: `docker-compose.yml` with Postgres 16; models and the first Alembic migration for `community`, `zone`, `node`, `link`, `app_user` (with codes, D-75). | `alembic upgrade head` builds an empty DB; `downgrade base` reverses it. | @agent-a | ✅ 2026-10-17 |
| M0.4 | Seed: community layout JSON in `backend/data/layouts/` (~20 nodes, zones, links with walking times, D-69), a background map image, 3 guards and 1 supervisor; `make seed` loads it. | Running `make seed` twice leaves the same rows; a test validates the layout file. | @agent-a | ✅ 2026-10-17 |
| M0.5 | API: `GET /session/users` for the role picker, `POST /session` (D-76; returns the token and the community ID) and `GET /communities/{id}/layout`; the layout route rejects a missing token with 401. | API tests cover all three routes and the 401. | @agent-a | ✅ 2026-10-17 |
| M0.6 | Frontend scaffold: Vite + React 19 + TypeScript + Tailwind + TanStack Query + Zustand + router; API client (`VITE_API_URL`, bearer token); `make types` from `openapi.json`. | `pnpm build` passes with the generated types. | @agent-a | ✅ 2026-10-17 |
| M0.7 | Role picker and read-only map: choose a seeded user, then see nodes, links and zones in react-konva over the background. | Locally, both roles reach the 20-node map. | @agent-a | ✅ 2026-10-17 |
| M0.8 | Makefile: `dev`, `seed`, `test`, `lint`, `build`, `types` (`eval` and `demo` as stubs). | Every target runs in Git Bash on Windows and in CI. | @agent-a | ✅ 2026-10-17 |
| M0.9 | CI: `backend.yml` (ruff, pytest with a Postgres service, stale `openapi.json` check) and `frontend.yml` (oxlint, tsc, Vitest, build, stale types check); both skip their tests when their folder is unchanged (D-48); branch protection on `main` requires both. | Both workflows are green on `main`, and a docs-only PR can merge. | @agent-a | ✅ 2026-10-19 |
| M0.10 | Deploy (D-47): backend to Cloud Run with PostgreSQL 16 on Neon (migrate and seed on start); frontend to Vercel with `VITE_API_URL`; CORS locked to the Vercel origin. | The deployed URL shows the seeded map on a laptop and a phone. | @agent-a | ⛔ waits on H2 |

### M1 · Draw and keep a layout (F1) — target Sun 18 Oct

Slice: a supervisor adds a camera, drags it, links two cameras with walking times, saves, refreshes, and sees the same layout.
Needs: D-63, D-64, D-65.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M1.1 | Layout validation: self-link → 422, duplicate → 409 (direction rule D-65), `0 < travel_min_s ≤ travel_max_s`, unknown node → 422. | Unit tests cover every rejection. | @agent-a | ✅ 2026-10-20 |
| M1.2 | `PUT /communities/{id}/layout` in one transaction, plus `POST/PATCH/DELETE` for `/nodes` and `/links`; supervisor only. | API tests: a saved layout reads back identical; 409, 422 and a guard's 403 return the D-40 body. | @agent-a | ✅ 2026-10-20 |
| M1.3 | JSON export and import (`GET …/export`, `POST …/import`). | Export → import → export gives an identical file. | @agent-a | ✅ 2026-10-20 |
| M1.4 | Editor canvas: add, drag and delete cameras and sensors; set heading; properties panel (name, code, kind, zone per D-64). | Each action works in the browser and survives a save. | @agent-a | ✅ 2026-10-20 |
| M1.5 | Link tool: pick node A, then B, enter min and max walking time; server errors show as a visible message. | A self-link and a duplicate are refused on screen. | @agent-a | ✅ 2026-10-20 |
| M1.6 | Save, reload, export and import buttons, with an unsaved-changes marker. | After a save and a browser refresh, the layout is identical. | @agent-a | ✅ 2026-10-20 |
| M1.7 | Timed check: build a 20-node layout from blank. | Done in ≤5 min; time recorded in PROGRESS.md. | @agent-a | ✅ 2026-10-20 |

### M2 · Play a scenario (F2) — target Mon 19 Oct

Slice: pick a scenario, press play, and watch events light up cameras in a live feed; pause and reset work.
Needs: D-52, D-53, D-54, D-70, D-71, D-77.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M2.1 | Scenario JSON format and loader; S1 and S2 scripts (D-15) with background traffic (D-71), local times (D-54) and in-file ground truth (D-70). | Both files load and validate; loader tests pass. | @agent-a | ✅ 2026-10-20 |
| M2.2 | Simulated clock and player: a pure core turns a scenario into an ordered event list; an async player emits it at the chosen speed, with pause and resume. | Two runs give an identical event sequence (golden event file). | @agent-a | ✅ 2026-10-20 |
| M2.3 | Migration for `scenario`, `scenario_run`, `event`; `POST /events` batch ingest validated against the contract; `GET /events` filters. | A valid batch is stored; a malformed or extra-field event gets 422. | @agent-a | ✅ 2026-10-20 |
| M2.4 | Run control: `POST /scenario-runs`, `/pause`, `/resume`, `/reset` (clears that run's derived rows); one live run per community (D-77). | API tests cover each state change. | @agent-a | ✅ 2026-10-20 |
| M2.5 | SSE: `GET /stream?run_id=` sends `event` messages; a fetch-based client hook in the frontend with the bearer token and reconnect. | Events arrive in the browser during a run. | @agent-a | ✅ 2026-10-20 |
| M2.6 | Player UI: pick a scenario, play, pause, reset, speed; live event feed; cameras flash on the map. | S1 and S2 play, pause and reset with one click each. | @agent-a | ✅ 2026-10-20 |

### M3 · Events become a path (F3) — target Tue 20 Oct

Slice: during playback a line grows across the map between cameras and carries an anonymous ID; a sighting outside the window starts a new path.
Needs: D-55, D-56.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M3.1 | Path linker (pure): window join (D-17), class match, vehicle factor (D-55), best time fit, anonymous IDs. | Unit tests: in-window join, early or late → new track, unlinked camera → new track, two competing objects. | @agent-a | 🔄 |
| M3.2 | Golden path files for S1 and S2. | `make test` fails when either scenario's paths change. | @agent-a | 🔄 |
| M3.3 | Migration for `track`, `track_segment`; ingest → linker → DB; `track_update` over SSE; `GET /tracks`, `GET /tracks/{id}`. | A track reads back with ordered segments. | @agent-a | 🔄 |
| M3.4 | Path overlay: a growing line between cameras, labelled with the anonymous ID. | In S2 one line follows the person across cameras. | @agent-a | 🔄 |
| M3.5 | Track lifecycle and expiry (D-56): close rule, `expires_at`, purge job. | With a short TTL, an expired track returns 404 after the purge. | @agent-a | 🔄 |

### M4 · A path raises an alert on the guard screen (F4, F5, F6) — target Wed 21 Oct

Slice: as the scripted night movement unfolds, a guard sees an alert card within 2 s with the rule, the suggested next camera and a map highlight, and confirms or dismisses it with a reason.
Needs: D-57, D-58, D-59, D-60, D-67.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M4.1 | Rule engine (pure): `after_hours`, `loiter`, `off_route` (D-52–D-54); each anomaly carries its rule and evidence event IDs. | Unit tests per rule, including each threshold's boundary. | | ⬜ |
| M4.2 | Migration for `rule_config` (seeded), `anomaly`, `alert`, `alert_action`; `GET /rules`, `PUT /rules/{key}`. | Changing a threshold through the API changes the outcome with no code change. | | ⬜ |
| M4.3 | Router (pure): nearest on-duty guard (D-58), supervisor escalation, next-camera score with basis (D-57). | Unit tests: nearest guard wins; no guard → escalated; next camera and basis returned. | | ⬜ |
| M4.4 | Wire anomalies into alerts with de-duplication (D-59) and rule-based severity (D-60); `alert` and `alert_update` over SSE; `GET /alerts`, `GET /alerts/{id}`. | Golden tests: S1 and S2 raise exactly their expected alerts. | | ⬜ |
| M4.5 | Guard console: alert cards (location, rule, severity, next camera), map highlight, notification cue. | 5 alerts fit without scrolling at 1366×768 (D-67). | | ⬜ |
| M4.6 | Actions: `POST /alerts/{id}/actions` (confirm or dismiss, one-line reason); status syncs to every open screen. | One click plus a reason updates the card in two open browsers. | | ⬜ |
| M4.7 | Latency check: Playwright times event ingest → card on screen. | ≤2 s on the deployed app. | | ⬜ |

### M5 · The agent ranks and explains (F7) — target Thu 22 Oct, then code freeze

Slice: the alert card shows a severity and a reason; after the run, an Incident timeline tab lists dated entries, each linking to its events.
Needs: D-61, D-62, D-74, D-79, D-80.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M5.1 | Vertex AI client: google-genai wrapper with timeout, rule-based fallback, and record/replay of responses (D-74). | With a fake client, a timeout yields the fallback; replay mode makes no network call. | | ⬜ |
| M5.2 | The five agent tools, read-only, as the agent's only data access (D-33). | Unit test per tool. | | ⬜ |
| M5.3 | Triage: prompt and JSON schema (severity, reason ≤3 sentences), run on alert creation, delivered per D-61. | The card shows the agent's severity and reason; invalid output falls back. | | ⬜ |
| M5.4 | Timeline: prompt, validator (D-23), `timeline_entry` migration, `POST/GET /alerts/{id}/timeline`, `timeline_ready` at run end (D-62). | Validator tests: an uncited entry is dropped; thin evidence yields an `unknown` entry. | | ⬜ |
| M5.5 | Timeline tab: dated entries that open their events, guard actions included. | After S2 the tab lists entries that each open their events. | | ⬜ |
| M5.6 | Wording check: agent output for both scenarios makes no identity or intent claim (D-24). | A test over recorded outputs passes a banned-terms list. | | ⬜ |
| M5.7 | Code freeze: tag the commit (D-07). | Tag pushed; fixes only from here. | | ⬜ |

### M6 · Evaluate, record, submit (F8) — target Fri 23 Oct, 23:59

Slice: run `make eval` or open the Eval page and read the results against the baseline; then record and submit.
Needs: D-68, D-72, D-73.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M6.1 | Eval runner on the same engine (D-35): four metrics plus baseline (D-26, D-68, D-72, D-73); `make eval` prints the report. Can start once M4 lands. | One command prints all four metrics and baselines for S1 and S2. | | ⬜ |
| M6.2 | `eval_result` migration, `POST /eval-runs`, `GET /eval-runs/{id}/report`, Eval page. | The page shows the same numbers as `make eval`. | | ⬜ |
| M6.3 | `docs/DEMO_SCRIPT.md` and a Playwright run that follows it (`make demo`). | `make demo` passes against the deployed URL. | | ⬜ |
| M6.4 | (human) Record the 5-minute demo from the deployed app (D-03). | Video uploaded; its link opens when logged out. | | ⬜ |
| M6.5 | (human) Pitch deck, at most 10 pages, with the eval numbers and the privacy stance. | Deck exported as PDF. | | ⬜ |
| M6.6 | (human) Submit the deck, video link and code link. | Submitted before 23 Oct 23:59. | | ⬜ |

### Human track

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| H1 | (human) Register the team. | Registered before registration closes on 21 Oct. | | ⬜ |
| H2 | (human) Neon, Vercel and GitHub accounts ready for M0.10; Google Cloud billing comes with H3. | A Neon project exists, and Cloud Build and Vercel can deploy from this repo. |  | 🔄 |
| H3 | (human) Google Cloud setup (D-80). | Vertex AI is enabled and the API's service account has the Vertex AI User role by 20 Oct. |  | ✅ 2026-10-19 |

## Phase 2 — after the Top 10 (28 Oct), final submission 11 Nov

An outline; each milestone gets a detailed plan once the team is through.

| ID | Task | Done when | Owner | Status |
|---|---|---|---|---|
| M7.1 | F9: `PATCH /nodes/{id}` to offline, an editor toggle, blind-spot shading. | An offline node shows as a blind spot. | | ⬜ |
| M7.2 | F9: the linker infers through an offline node via its neighbours. | Unit tests cover the skip-over join. | | ⬜ |
| M7.3 | F9: scenario S3 (key camera offline) with a golden file. | S3 runs end to end with a blind-spot marker. | | ⬜ |
| M8.1 | (human) F10: choose a public clip whose licence allows competition use (PRD Q4); note source and licence in `backend/data/video/`. | Licence note committed. | | ⬜ |
| M8.2 | F10: an offline YOLO + ByteTrack script maps detections to nodes and posts events; it stores no frames. | The clip's events land in `/events`. | | ⬜ |
| M8.3 | F10: play the clip's events through the existing screens. | Events appear in the feed; no face is stored or shown. | | ⬜ |
| M9.1 | F13: build `baseline_profile` from simulated and public-video events (PRD Q5). | Profiles exist per camera and hour. | | ⬜ |
| M9.2 | F13: rules read the baseline; supervisor overrides win. | A test shows an override beating the learned value. | | ⬜ |
| M9.3 | F13: the eval report compares false alerts with and without the baseline. | False alerts drop on the same scenarios. | | ⬜ |
| M10.1 | F11: `GET /paths/query?from=&to=` and a query form. | One path and its timeline return within 10 s. | | ⬜ |
| M10.2 | F12: `retention_policy`, `PUT /retention`, purge with logged deletions. | Data past retention disappears and the deletion is logged. | | ⬜ |
| M10.3 | F12: `audit_log` for every query and action; `GET /audit-log` view. | Every query and confirmation appears with user, time and target. | | ⬜ |
| H4 | (human) Interview a security company supervisor (PRD Q7). | Notes in `docs/` by 6 Nov. | | ⬜ |
| H5 | (human) Final submission; pitch on 14 Nov. | Submitted by 11 Nov. | | ⬜ |
