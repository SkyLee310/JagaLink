# JagaLink

Community early-warning safety network. JagaLink links a guarded community's isolated CCTV cameras and sensors into one spatial graph, so anonymous movement paths alert the nearest guard early, name the next camera to check, and can be traced after an incident — all without facial recognition.

Prototype for the Sime Darby Property University Hackathon 2026 (Township of Tomorrow · People / Safety & Security).

## Run it locally

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22.12+ with pnpm, GNU make (Windows: `winget install ezwinports.make`).

```bash
make install   # backend and frontend dependencies
make dev       # Postgres in Docker, API on :8000, web app on http://localhost:5173
```

`make test`, `make lint`, `make build` and `make types` cover the rest; see `AGENTS.md`.

## Prototype limits

- **No real login.** You pick a seeded guard or supervisor; authentication is out of scope for this prototype.
- **Privacy by construction.** No faces, plates, images or personal data are stored; paths use anonymous IDs that expire.
- **Simulated community.** "Taman Simulasi" is a fictional township drawn for this project.

## Docs

| File | Holds |
|---|---|
| `docs/PRD.md` | Product, features F1–F13, acceptance criteria |
| `docs/TECH_SPEC.md` | Architecture, data model, API, milestones |
| `docs/DECISIONS.md` | Locked decisions |
| `docs/TASKS.md` | Milestone tasks and status |
