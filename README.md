# SurakshaNet AI

> **Smart Predictive Public Safety Platform**
> AI · IoT · Edge Computing · Real-Time Response

A working MVP of an end-to-end intelligent surveillance and public-safety
system: detects threats from multi-modal sensors, predicts crime hotspots,
broadcasts alerts to operators and police, and gives citizens a one-tap SOS
panic button.

This repository ships **real, runnable code** — not slideware:

- **Backend** — FastAPI + async SQLAlchemy, JWT auth with RBAC, WebSocket
  pub/sub, sensor-driver abstractions, multi-modal AI fusion engine, crime
  prediction heatmap, dispatch recommender, audit log.
- **Frontend** — React + TypeScript + Vite + Tailwind. Live multi-camera
  console, dark Leaflet map with real-time heatmap overlay, dispatch panel,
  telemetry & metrics, citizen PWA with SOS button.
- **Simulation engine** — Replayable scenarios that exercise the full
  capture → analyze → fuse → alert → dispatch pipeline.
- **Docker compose** — One-command deployment of frontend + backend.

> Read the full design in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
> the API surface in [`docs/API.md`](docs/API.md).

---

## Quick start (laptop, no Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# OpenAPI: http://localhost:8000/docs
```

The first run seeds:

- 5 demo smart poles around Hyderabad coordinates.
- 4 demo accounts (admin / operator / police / citizen) — see
  [`docs/API.md`](docs/API.md) for credentials.
- A live simulation tick that produces sensor readings every ~2s.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Operator console: http://localhost:5173
# Citizen PWA:      http://localhost:5173/citizen
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`. The
WebSocket hub connects directly to the backend.

### 3. Drive a demo

1. Log in as **operator** (`operator@suraksha.local` / `Operator123!`).
2. Open the **Overview** page and click any scenario in the *Scenario
   Injector* card — e.g. *Street fight with shouting*.
3. Watch the new incident appear on the dashboard and the map heatmap
   recompute.
4. Open the **Dispatch** page, select the incident, and assign a unit.
5. Advance the assignment through *en_route → on_scene → cleared* — the
   incident auto-resolves.
6. Try the citizen SOS at `/citizen` — anonymous SOS materialises a
   `panic_sos` incident immediately.

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest          # 8 tests: fusion + API + scenarios + heatmap
ruff check .    # lint
```

## Docker compose

```bash
docker compose up --build
# frontend → http://localhost:5173
# backend  → http://localhost:8000
```

## Project layout

```
surakshanet-ai/
├── backend/                    FastAPI service + AI + simulation
│   ├── app/
│   │   ├── api/                routers (auth, incidents, dispatch, …)
│   │   ├── ai/                 vision, audio, fusion
│   │   ├── alerts/             alert manager
│   │   ├── auth/               JWT + RBAC
│   │   ├── db/                 async SQLAlchemy models
│   │   ├── dispatch/           recommender + units
│   │   ├── engine/             event bus + incident pipeline
│   │   ├── prediction/         heatmap engine
│   │   ├── sensors/            HW abstractions (camera/audio/motion/panic/telemetry)
│   │   └── services/           audit log, etc.
│   ├── simulations/            replayable scenarios
│   └── tests/                  pytest suite
├── frontend/                   React + TS + Vite + Tailwind
│   └── src/pages/              Login · Dashboard · Live · Map · Dispatch · Telemetry · Citizen
├── ai_models/                  drop-in trained models go here
├── datasets/                   training data scaffold
├── deployment/                 Dockerfiles + nginx config
├── docs/                       ARCHITECTURE.md, API.md
└── docker-compose.yml
```

## Configuration

All settings can be overridden via environment variables (see
[`.env.example`](.env.example)) — Pydantic Settings reads `backend/.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `JWT_SECRET` | `change-me…` | HS256 secret. **Override in production.** |
| `DATABASE_URL` | `sqlite+aiosqlite:///./surakshanet.db` | Use Postgres in prod. |
| `ENABLE_SIMULATION_ON_STARTUP` | `true` | Drive sensors on boot. |
| `SIMULATION_TICK_SECONDS` | `2.0` | Per-pole tick rate. |
| `ENABLE_YOLO` | `false` | Switch to real YOLOv8 detection. |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.55` | Per-modality cutoff. |
| `FUSION_ALERT_THRESHOLD` | `0.65` | Final alert cutoff. |

## MVP success metrics

The dashboard surfaces (and the API exposes at `/api/telemetry/metrics`):

- Detection accuracy (target ≥ 94%)
- Inference FPS (target 30)
- Average + P95 alert-path latency (sub-200 ms goal)
- False-positive rate
- Open / total incidents, alerts, poles online

## Future / stretch

- Drone integration via a new `Sensor` subclass (`DroneFeed`) plus a fleet
  layer in dispatch.
- Facial recognition plug-in: a second `VisionDetector` consumed by fusion.
- Federated edge learning across poles (FedAvg over local YOLO fine-tunes).
- LoRa pole-to-pole comms: HW driver under `app.sensors.lora`.
- RL patrol optimiser: replace the greedy patrol planner.

## License

MIT — see [`LICENSE`](LICENSE).
