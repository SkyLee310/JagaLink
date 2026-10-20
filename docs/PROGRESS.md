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
