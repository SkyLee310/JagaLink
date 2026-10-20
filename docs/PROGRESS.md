# PROGRESS.md — Session log

One entry per milestone or working session, newest last: what changed, the implementation decisions behind it, and ⚠️ traps for the next session (AGENTS.md).

## 2026-10-16 → 20 · M0 walking skeleton

**Status.** M0.1–M0.9 done and merged (PRs #1–#3). M0.10, the first deploy, waits on H2; the steps are under "Still to do" below.

**What changed**
- Public repo `SkyLee310/JagaLink` (D-81). Branch protection on `main` requires the `backend` and `frontend` checks; no reviews. PR #2, which changed only docs, merged with both jobs skipped (M0.9).
- Backend: FastAPI under `/api/v1` with health, session and layout routes; every failure, a 500 included, answers `{code, message, details}` (D-40); HMAC session tokens (D-76).
- Database: migration `0001` (community, zone, node, link, app_user). The seed loads Taman Simulasi: 6 zones, 20 nodes, 23 links, 4 users.
- Frontend: role picker, then the console with a read-only react-konva map; the API client sends the bearer token; types are generated from `backend/openapi.json` (D-42).
- `Makefile`; CI workflows that skip their job when their folder is unchanged (D-48); `backend/Dockerfile` (migrate, seed, then uvicorn on `$PORT`); `frontend/vercel.json` (SPA rewrite).
- Hosting moved from Railway to Cloud Run plus Neon (D-47, PRs #2 and #3).
- Google Cloud project `jagalink-hackathon` (number 77919092302, D-80):
  - APIs enabled: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Vertex AI and Billing Budgets;
  - service account `jagalink-api@jagalink-hackathon.iam.gserviceaccount.com`, with Vertex AI User and access to both secrets;
  - secret `session-secret` set; secret `database-url` created, but it has no version yet;
  - budget alert of RM 25, at 50, 90 and 100 %.

**Implementation decisions**
- Seeded rows get `uuid5` IDs derived from their codes, so every database holds the same IDs. `python -m app.db.seed` inserts only when the community is missing, so edits survive a redeploy; `--reset` reloads a clean demo state (D-27).
- The session token carries the user ID, role, community ID and expiry. The frontend keeps it in `sessionStorage`, so each browser tab can hold a different role.
- `GET /api/v1/health` answers 503 `{status: degraded, db: down}` when the database is unreachable.
- Settings refuse the dev `SESSION_SECRET`, or one under 32 characters, in prod. They rewrite `postgresql://` to `postgresql+psycopg://`, and validation errors leave out the input, which holds the database password.
- The map world is 1200 × 800 px at 0.25 m/px. Labels hide below 60 % scale.

**⚠️ Traps**
- GNU make from winget is not on Git Bash's `PATH`. Prefix commands with `export PATH="/c/Users/Sky Lee/AppData/Local/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$PATH"`.
- The Windows console is cp1252, so printing non-ASCII from Python fails. Write such output to a UTF-8 file instead.
- A pipe hides the exit code, and `2>&1 | wc -l` counts error lines too: a "no versions" error once read as one secret version. Check `$?`, or print the command's output itself.
- gcloud's default project on this machine is `skyfin`. Always pass `--project jagalink-hackathon`.
- The budget is in MYR, the billing account's currency.
- `astral-sh/setup-uv` has no major-version tags after v7, so pin a full release tag (`v10.3.0`).
- `gh pr merge --match-head-commit` needs the full 40-character SHA.
- No git credential helper is stored. Push with `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push …`.
- Konva draws after the first paint, so a screenshot taken at once can show an empty map.
- Harmless warnings:
  - `pnpm build` warns about a ~690 kB chunk (react-konva);
  - openapi-typescript 7 warns about its TypeScript peer range, but works with TS 6;
  - FastAPI's `TestClient` warns about httpx deprecations.
- On Vercel, pnpm 12 comes from `packageManager` only when the project sets `ENABLE_EXPERIMENTAL_COREPACK=1`.
- Cloud Run gets a startup probe only. A periodic probe on `/api/v1/health` would keep Neon awake and use up its free compute hours.
- `DATABASE_URL` must be Neon's direct (unpooled) URL, `postgresql://…?sslmode=require`, saved without a trailing newline.
- The Vercel connector in this environment gets 403 when it creates a project, and the Vercel CLI is not installed. Create the Vercel project in the dashboard.

**Still to do for M0.10 (H2)**
1. Add the Neon direct URL as a version of the `database-url` secret in `jagalink-hackathon`.
2. In Vercel, import `SkyLee310/JagaLink` as project `jagalink`, with root directory `frontend`, and set these environment variables:
   - `VITE_API_URL=https://jagalink-api-77919092302.asia-southeast1.run.app` (Cloud Run's fixed URL for this service);
   - `ENABLE_EXPERIMENTAL_COREPACK=1`.
3. Deploy the API from a clean export of `main`:
   - Export: `git archive main backend | tar -x -C <dir>`.
   - Deploy: `gcloud run deploy jagalink-api --source <dir>/backend --region asia-southeast1 --project jagalink-hackathon --service-account jagalink-api@jagalink-hackathon.iam.gserviceaccount.com --max-instances 1 --timeout 3600 --set-env-vars APP_ENV=prod,FRONTEND_ORIGIN=<Vercel production URL> --set-secrets DATABASE_URL=database-url:latest,SESSION_SECRET=session-secret:latest --allow-unauthenticated`.
   - Add a startup probe on `/api/v1/health`.
4. Check the seeded map at the Vercel URL on a laptop and a phone.

## 2026-10-20 · M1 draw and keep a layout (F1)

**Status.** M1.1–M1.7 done (PR #5). The deployed check waits on M0.10, like every milestone.

**What changed**
- Backend:
  - a pure layout checker, `app/engine/layout.py`;
  - `PUT /communities/{id}/layout` saves the whole layout in one transaction;
  - `POST`, `PATCH` and `DELETE` on `/nodes` and `/links`, plus `GET …/export` and `POST …/import`; every write is supervisor-only (D-66);
  - migration `0002` adds `community.code`, `community.normal_routes` and `link.distance_m`.
- Frontend: `/editor` for supervisors, with:
  - a Konva canvas with select, camera, sensor and link tools, dragging and a heading handle;
  - a properties panel;
  - save, reload, export, import and clear, an unsaved-changes marker and keyboard shortcuts;
  - server refusals listed on screen.
- Browser check (local API on PostgreSQL 16, 1366 × 768): a camera was added, renamed, turned, dragged and linked, and the self-link and duplicate attempts were refused. After a save and a page refresh the layout was identical; the camera was then deleted and Ctrl+S saved the result.
- M1.7: a scripted click-through in the browser built 20 cameras and 23 links from blank and saved them in 1.9 s (69 clicks). At about 3 s per click a person needs about 3.5 min, inside the 5-minute target. A hand-timed run is still worth doing before the recording.

**Implementation decisions**
- A save answers 409 when every problem is a duplicate (code or link), else 422; `details.problems` lists every problem.
- The client generates node and link UUIDs. A save upserts nodes by ID, so events and users keep pointing at them; renamed codes first move to `~{id}`, so two nodes can swap codes; normal routes follow renames.
- Import matches nodes by code; export writes codes only (D-75), in a canonical order, so export → import → export is identical.
- A new link gets walking times from the straight-line distance: `floor(d / 1.4)` to `ceil(d / 1.2)` seconds, like the seed. A link that reverses a one-way link is added as one-way, with a notice (D-65).
- A node takes the zone under it when it is placed or dropped.
- Notices float over the map, so the map keeps its size and nodes stay under the pointer.

**⚠️ Traps**
- Docker Desktop fails to start on this machine: `%LOCALAPPDATA%\Docker\run` holds stale sockets. Quit Docker, then delete that folder or reboot.
- Until Docker is fixed, the EDB PostgreSQL 16 Windows binaries (a zip, no installer) do the job:
  1. `initdb -U jagalink --pwfile=<file holding jagalink>`;
  2. run `postgres -D <data dir> -p 5432`;
  3. `CREATE DATABASE jagalink`.
  `make db`, `make seed` and `make test` call Docker, so run their inner commands instead, e.g. `cd backend && uv run alembic upgrade head`.
- Every layout write must be checked against the community's zones. An empty zone list fails every zoned node with `unknown_zone`; CI caught this in PR #5.
- The browser pane's screenshot can show a frame from before the last clicks. Read the DOM, or take a second screenshot, before calling something a bug.

## 2026-10-20 · M2 play a scenario (F2)

**Status.** M2.1–M2.6 done (PR #6). The deployed check waits on M0.10.

**What changed**
- Scenarios: `backend/data/scenarios/` holds S1 (vehicle circling the south lanes, evening) and S2 (person over the back fence at night). Each file has background traffic (D-71), local times (D-54) and in-file ground truth (D-70). Golden event files in `golden/` pin each whole night; `uv run python -m app.sim.golden` rewrites them.
- Backend:
  - pure core: `engine/clock.py` (simulated clock), `sim/script.py` (scenario → ordered event list), `engine/events.py` (the event literals shared by every module);
  - migration `0003`: `scenario`, `scenario_run` and `event`, with one live run per community enforced by a partial unique index (D-77);
  - `POST /events` batch ingest and `GET /events` filters; `GET /scenarios`; `POST /scenario-runs`, `GET /scenario-runs/current`, `GET /scenario-runs/{id}`, and `/pause`, `/resume`, `/reset`;
  - `GET /stream?run_id=`: Server-Sent Events, the stored backlog first, then live `event` messages and keep-alive comments;
  - the seed loads both scenarios; `tzdata` gives Windows the IANA zones (D-78).
- Frontend: `/player` for supervisors:
  - scenario and speed pickers, Play, Pause and Reset, a ticking clock, a progress bar and an event count;
  - a live event feed (time, camera, type, class, per-camera ID);
  - the map rings each camera with an object in view and flashes it when an event arrives;
  - `api/sse.ts`, a fetch-based SSE client that sends the bearer token and reconnects with backoff; `lib/liveRun.ts` folds messages into the feed and map state.
- On a phone the header's page links take their own row, and the player page scrolls.
- Browser check (local API on PostgreSQL 16):
  - at 1366 × 768, S1 played at 10×, paused with the clock frozen at 24/50 events, resumed at 120×, finished at 50/50, then reset to Ready with an empty feed;
  - S2 at 60× lit the north fence sensor, then the back-lane and lane 2 cameras, and finished at 15/15; Reset worked;
  - at 375 px wide the page has no horizontal scroll.

**Implementation decisions**
- An event's `node_id` is the node's UUID, like every other API body (D-40). TECH_SPEC's example event shows a code; that example is illustrative only.
- The player is an asyncio task on the app's event loop. Routes stay sync and reach the loop with `run_coroutine_threadsafe`. Each emitted batch goes through the same `event_store.ingest` as `POST /events`, then the hub publishes it to the run's SSE subscribers.
- The hub keeps a per-run message log. A subscriber gets the stored backlog first, so a late join or a reconnect sees the whole run. Reset, or a new run replacing the old one, closes the stream; the client reconnects and starts from an empty feed.
- Starting a run stops the community's current live run and puts the guards at the posts in the scenario's roster.
- After an API restart a run that was playing comes back paused. Resume continues from the stored event count and the last event time.
- The page polls the current run every second while it plays and ticks the clock between polls at the run's speed.
- An event's `attrs` hold at most 10 short scalar values, and keys that name identity (face, name, plate, IC, phone…) are refused (D-10, privacy by construction).
- `uvicorn` runs with `--timeout-graceful-shutdown 3` (Makefile and Dockerfile), so an open SSE stream cannot block a reload or a Cloud Run shutdown.

**⚠️ Traps**
- pytest's `tmp_path` fixture fails here with a `PermissionError` on `…\Temp\pytest-of-Sky Lee`. Keep tests off it.
- `pyproject.toml` already sets `addopts = "-q"`; another `-q` hides the summary line.
- API tests share one DB session with the player. A route must not touch the DB after it starts a player. Set `InstantTimer` on the run manager before starting a run (swapping it later does nothing), and wait with `client.portal.call(manager.wait, run_id)`.
- SQLAlchemy 2.1: `Result.tuples()` is deprecated and `dict(result)` fails; build dicts with a comprehension over the rows.
- FastAPI wraps included routes as `_IncludedRouter`; list paths with `app.openapi()`.
- The Vite dev server's Tailwind missed every class in a feature folder created while it ran. Restart `pnpm dev` after adding a folder.

## 2026-10-20 · M3 events become a path (F3)

**Status.** M3.1–M3.5 done (PR #7). The deployed check waits on M0.10.

**What changed**
- Backend:
  - `engine/linker.py`, the pure path linker: a deterministic state machine fed one sighting at a time (`feed`, `advance`, `finish`; `link_all` for a whole list). It joins by D-17 with the D-55 class factor, lets the best time fit win, and closes and expires tracks by D-56;
  - golden path files `golden/*.paths.jsonl` pin every track of each whole night; `uv run python -m app.sim.golden` rewrites them with the event files. Tests also check that each scripted object maps to exactly one track, and each target to one closed path through all its visits;
  - migration `0004`: `track` and `track_segment`, each segment with the IDs of the events behind it;
  - `core/pipeline.py`: every stored batch (player or `POST /events`) goes through the run's linker; changed tracks are written and pushed as `track_update` messages, and expired ones are deleted and pushed once more with status `expired`. When the run ends, its open tracks close;
  - `GET /tracks` (by run and status) and `GET /tracks/{id}` (404 `track_not_found` once purged); `TRACK_TTL_S` (default 86400) sets the TTL.
- Frontend: the player map draws each active path as a bright arrow along the links, tagged with its anonymous ID at the head (tags stack where paths meet). Closed paths stay faint and untagged; an expired path leaves the map.
- Browser check (local API on PostgreSQL 16, 1440 × 900):
  - S2 at 60×: one line grew from the north fence sensor through back-02 to lane-2n with its `obj-…` tag, then on through main-02 and lane-2s to the south fence, and turned faint when the run finished;
  - S1 at 60×: the vehicle's repeated loop drew as one tagged path round the south lanes and the main road.

**Implementation decisions**
- Expiry runs in event time (D-31): `expires_at = last_ts + TTL`, and after each batch the purge deletes every track of the community whose `expires_at` is at or before the batch's last event time. A wall-clock purge would delete the scenario-dated tracks (21 Oct) as soon as the real date passed them.
- IDs are deterministic. A track's ID is `uuid5(run_id, "track-<n>")`; its anonymous ID `obj-xxxxxx` steps an odd constant through 24 bits from a run-specific offset, so it never repeats within a run, and a rebuilt linker lands on the same rows.
- Each run's linker lives in memory. After a restart or a failed batch it is rebuilt from the run's stored events, so posted batches keep linking across restarts.
- A dwell or disappear with no appear before it starts a new track rather than being dropped. A track waiting off camera closes once the largest outgoing `travel_max_s` has passed; a track still in view stays open until the run ends.
- At the run's end, `finish` first advances the linker to the window end (expiring anything due), then closes every open track.
- `track_update` carries the whole track each time, so the client keeps only the latest version; a reconnect replays the run's log as before.

**⚠️ Traps**
- After pulling M3, run `make seed` (or `uv run alembic upgrade head` in `backend/`) on the dev database. A server still on migration 0003 fails every ingest because the `track` table is missing.
- D-56 says expiry clears `anomaly.track_id`: give that foreign key `ON DELETE SET NULL` in M4. `purge_expired` is a bulk `DELETE … RETURNING`, so ORM cascades never run; only database `ON DELETE` rules apply.
- The golden path files cover the whole night (71 tracks each), while a live run plays only its window (S1 50 events, S2 15 with one track), so a live run produces far fewer tracks.
- `preview_logs` on the API server can return tens of thousands of characters after a stack trace; restart the server rather than reading it all.

## 2026-10-20 · M4 a path raises an alert on the guard screen (F4, F5, F6)

**Status.** M4.1–M4.6 done (PR #8). M4.7 passes locally: 70 ms from posting the event to the card in the DOM, against a 2 s budget. The deployed run waits on M0.10: `E2E_BASE_URL=<Vercel URL> E2E_API_URL=<Cloud Run URL> PW_CHANNEL=msedge pnpm e2e` in `frontend/`.

**What changed**
- Backend:
  - pure engine: `engine/rules.py` (after-hours, loiter, off-route, D-52–D-54), `engine/router.py` (nearest on-duty guard by walking time, supervisor escalation, next-camera score with its basis, D-57, D-58) and `engine/alerting.py` (one alert state per track and rule). `link_and_check` is the one step that the pipeline, the golden files and the M6 eval runner share (D-35);
  - migration `0005`: `rule_config`, `anomaly`, `alert`, `alert_action`;
  - rules are seeded from the engine defaults (`RuleSet()`). `GET /rules` is open to every user. `PUT /rules/{key}` is for supervisors only and merges params field by field; bad thresholds get 422 `invalid_rule`, which lists each problem. The pipeline reloads the rules and guard posts on every batch, so an edit applies from the next event;
  - alerts: `alert_store.save` writes anomalies and alerts under deterministic IDs, after the tracks and before the purge. Routes: `GET /alerts` and `GET /alerts/{id}`, plus `POST /alerts/{id}/actions` to confirm or dismiss with a one-line reason of at most 200 characters (409 `alert_already_handled`). The stream carries `alert` and `alert_update`, and its backlog sends every alert as `alert_update`;
  - golden alert files `golden/*.alerts.jsonl`. Tests check that:
    - each target raises exactly its expected alerts;
    - background movement stays within 2 false alerts per camera (D-68);
    - the live window raises only the targets' alerts;
  - settings `NEXT_CAMERA_WEIGHTS` (D-57) and `MULTI_RULE_SEVERITY` (D-60);
  - the stream now starts with an `: open` comment line (see the traps).
- Frontend:
  - the guard console lists the run's alerts as cards beside the map, open and most severe first. Each card shows:
    - severity (dashed while provisional, D-61), rule, node and local time;
    - why the alert fired;
    - the next camera with distance, walk and share of normal routes;
    - who the alert went to and how far they have to walk;
  - the map rings each open alert in its severity colour and draws a dashed arrow to a dashed ring on the next camera;
  - the notification cue (F6):
    - a two-note Web Audio chime (`lib/cue.ts`), once per burst of new open alerts;
    - a 6 s glow on a new card;
    - the open-alert count in the tab title;
  - each open card has a reason box with Confirm and Dismiss. The answer updates the card at once, and every other screen updates through `alert_update`;
  - `lib/runTime.ts` moved out of the player, and `components/StreamBadge.tsx` is now shared by the event feed and the alert panel;
  - Playwright (`@playwright/test`, D-78): `playwright.config.ts` (1366 × 768) and `e2e/latency.spec.ts`, run with `pnpm e2e`.
- Browser check (local API, Edge through Playwright):
  - five open alerts fit with no scrolling at 1366 × 768, and also at 1366 × 641, which is a maximised browser on a 768-pixel screen;
  - Guard C confirmed one alert with a reason, and the supervisor's tab showed "Confirmed by Guard C … — “reason”". Both tab titles went from (5) to (4).

**Implementation decisions**
- An alert is one per (track, rule) for the track's lifetime (D-59). A repeat match adds evidence and raises `version`, even after someone has handled the alert; a handled alert never reopens.
- Severity is each rule's own `severity` param. Once two or more rules match a track, all its alerts take `MULTI_RULE_SEVERITY` (D-60). Severity stays provisional (`triage_status` `pending`) until M5's triage.
- With no guard on duty who can reach the node, the alert is `escalated` to the first on-duty supervisor, or the first supervisor if none is on duty.
- An action is stamped with the run's simulated clock (D-31), and never earlier than the alert, so the M5 timeline can place it.
- `version` rises with every change, and rows are locked while they change. Clients keep the highest version they have seen, so replays and the race between an action's answer and its `alert_update` both settle the same way.
- Both roles see every alert of the run, marked "(you)" where it went to the viewer, and every new open alert chimes. Filtering per guard can come later.
- The chime waits 150 ms so that a burst, or the replay on connect, makes one sound. Alerts that have chimed once stay quiet after a reconnect, and a reconnect keeps each card's first-seen time.

**⚠️ Traps**
- After pulling M4, run `make seed`. It applies migration 0005 and adds the three rule rows.
- `RunManager` now takes `pipelines=`, carrying the next-camera weights and the multi-rule severity; `main.py` builds it from settings.
- A late subscriber to a live channel gets the hub log's original `alert` messages after the backlog's newer `alert_update`, so the client must keep the highest version.
- `anomaly.track_id` is set only when the anomaly is created. Expiry nulls it (`ON DELETE SET NULL`), and the alert keeps its evidence.
- After an intended engine change, rewrite the golden files with `uv run python -m app.sim.golden`.
- Use the Edit tool for strings that contain backslashes. A Git Bash heredoc into Python turned `\n` into real newlines.
- Browsers launched by Playwright (Edge and Chrome here) did not resolve `fetch` on a streaming response until its first body byte, while the in-app browser and Python did. A console on a run with nothing to replay therefore sat at "Connecting…" until the 15 s ping. The stream's `: open` line fixes this, and proxies that wait for a body are helped too, so keep it first.
- Local e2e: `PW_CHANNEL=msedge pnpm e2e` (or `chrome`) uses the installed browser; `pnpm exec playwright install` is needed only where no browser is installed. The latency check replaces the community's current run (D-77), so never run it against the deployed app during a demo.
- These files were edited outside the M4 files row:
  - `backend/.env.example`, for the two new settings;
  - `frontend/playwright.config.ts`;
  - `frontend/vite.config.ts`, so Vitest reads only `src/**/*.test.*`;
  - `frontend/tsconfig.node.json`, which now type-checks `e2e/` with the DOM lib;
  - `frontend/pnpm-lock.yaml`.
