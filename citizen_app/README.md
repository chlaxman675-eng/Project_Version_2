# Citizen Safety App

The MVP citizen experience is a Progressive Web App (PWA) shipped inside the
main frontend bundle (`frontend/src/pages/CitizenPage.tsx`). It is reachable at
`/citizen` and provides:

- One-tap SOS panic button (anonymous and authenticated flows)
- GPS coordinates auto-fetched from the device
- Optional incident note
- Nearby safe-spot list (monitored poles + low-risk areas)
- Standalone install via `manifest.webmanifest` and the shield icon

To convert to a native React Native app later, the same `api.ts` module can be
reused with a thin shim around `localStorage` and `navigator.geolocation`.

The architecture is intentionally separated: the citizen app talks to the same
FastAPI backend (`/api/citizen/sos`, `/api/citizen/sos/anonymous`,
`/api/citizen/safe-zones`, `/api/citizen/safe-route`).
