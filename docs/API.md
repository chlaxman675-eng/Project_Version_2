# API Reference (overview)

Full interactive docs: <http://localhost:8000/docs> (Swagger UI) and
`/redoc`. All endpoints below are prefixed with `/api`.

## Auth

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| POST | `/auth/register` | `{email, full_name, password, role}` | role ∈ citizen/operator/police/admin |
| POST | `/auth/login` | OAuth2 form (`username`, `password`) | returns `access_token` |
| GET  | `/auth/me` | — | requires Bearer token |

Demo accounts seeded at startup:

| Role | Email | Password |
| --- | --- | --- |
| admin    | `admin@suraksha.local`    | `SurakshaAdmin123!` |
| operator | `operator@suraksha.local` | `Operator123!`       |
| police   | `officer@suraksha.local`  | `Police123!`         |
| citizen  | `citizen@suraksha.local`  | `Citizen123!`        |

## Incidents

- `GET /incidents?status=&limit=` — list
- `GET /incidents/{id}` — detail
- `POST /incidents/{id}/status` — update status (operator/police/admin)

## Alerts

- `GET /alerts` — recent alerts feed

## Dispatch

- `GET /dispatch/units`
- `GET /dispatch/assignments`
- `POST /dispatch/assign` `{incident_id, unit_id, notes}` (operator/police/admin)
- `POST /dispatch/assignments/{id}/status` `{status}` (operator/police/admin)

## Prediction

- `GET /prediction/heatmap`
- `GET /prediction/risk-zones?top_n=`
- `GET /prediction/patrol-recommendations`

## Citizen

- `POST /citizen/sos` `{latitude?, longitude?, note?, pole_id?}` (auth)
- `POST /citizen/sos/anonymous` (no auth)
- `POST /citizen/report`
- `GET  /citizen/safe-zones`
- `GET  /citizen/safe-route?from_lat=&from_lon=&to_lat=&to_lon=`

## Simulation

- `GET  /simulation/scenarios`
- `POST /simulation/inject` `{scenario, pole_id?}` (operator/admin)
- `POST /simulation/inject-public` (no auth, demo)
- `POST /simulation/start|stop` (operator/admin)

## Telemetry

- `GET /telemetry/health`
- `GET /telemetry/metrics`

## Poles

- `GET /poles`

## WebSocket

`ws(s)://<host>/api/ws`

Topics broadcast on the bus:

| Topic | Payload |
| --- | --- |
| `incident.created` | `{incident, alert_id, dispatch_recommendation}` |
| `alert.created` | `{alert_id, incident_id}` |
| `dispatch.assigned` | `{assignment_id, incident_id, unit_id, eta_seconds, by}` |
| `dispatch.updated` | `{assignment_id, status}` |
| `inference` | `{pole_id, vision[], audio[], scene, timestamp}` |
| `telemetry` | `{pole_id, data, timestamp}` |
| `simulation.injected` | `{scenario, title, pole_id}` |
