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
