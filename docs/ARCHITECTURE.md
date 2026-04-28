# SurakshaNet AI — Architecture

```
                                                                        
       ┌────────────┐    ┌──────────────┐    ┌────────────────────┐    
       │ Smart Pole │    │ Citizen PWA  │    │  Operator Console  │    
       │ (sensors)  │    │  (React)     │    │   (React + Map)    │    
       └─────┬──────┘    └──────┬───────┘    └──────────┬─────────┘    
             │                  │                       │              
   sensor    │  HTTPS (REST)    │ WS                    │ WS + REST    
   readings  ▼                  ▼                       ▼              
        ┌─────────────────────────────────────────────────────┐        
        │                    FastAPI Backend                   │       
        │   /api/auth /api/incidents /api/dispatch  /api/ws    │       
        │   /api/prediction  /api/citizen  /api/simulation    │        
        └────┬──────────────┬──────────────┬───────────────────┘       
             │              │              │                            
   ┌─────────┴───┐   ┌──────┴──────┐  ┌────┴─────────────┐             
   │ Sensor Drv  │   │   AI Layer  │  │ Prediction Eng.  │             
   │ (HW abstr.) │   │ Vision/Audio│  │ Heatmap+Patrol   │             
   └─────────┬───┘   │  + Fusion   │  └────┬─────────────┘             
             │       └──────┬──────┘       │                            
             ▼              ▼              ▼                            
        ┌──────────────────────────────────────────────┐               
        │           In-process Event Bus (pub/sub)       │             
        │   topics: inference, telemetry, incident.*,   │             
        │           alert.*, dispatch.*, simulation.*   │             
        └────────────────────────┬─────────────────────┘               
                                 │                                      
                ┌────────────────┴───────────────┐                     
                ▼                                 ▼                     
        ┌──────────────┐                 ┌─────────────────┐           
        │  SQLite/PG   │                 │ WebSocket Hub   │           
        │  + Audit Log │                 │ (live UI feed)  │           
        └──────────────┘                 └─────────────────┘           
```

## Layers

1. **Smart Pole / Sensor Layer** (`backend/app/sensors/`)
   Hardware-abstraction interfaces: `Sensor`, `CameraSensor`, `AudioSensor`,
   `MotionSensor`, `PanicButtonSensor`, `TelemetrySensor`. The MVP simulates
   readings; subclasses can plug in Raspberry Pi GPIO, Jetson CSI cameras,
   USB mics, etc.

2. **Edge AI Detection Engine** (`backend/app/ai/`)
   - `VisionDetector` — `MockVisionDetector` (scene → label) or `YoloDetector`
     (YOLOv8) when `ENABLE_YOLO=true`.
   - `AudioClassifier` — rule-based; replaceable with YAMNet/PANNs.
   - `FusionEngine` — probabilistic-OR late fusion + co-occurrence boosts.

3. **Crime Prediction Engine** (`backend/app/prediction/heatmap.py`)
   Temporally-decayed grid heatmap, top-K risk zones, greedy nearest-neighbour
   patrol plan. Endpoints: `/heatmap`, `/risk-zones`, `/patrol-recommendations`.

4. **Backend Command System** (`backend/app/`)
   FastAPI + SQLAlchemy async. Routers: auth, incidents, alerts, dispatch,
   prediction, citizen, simulation, telemetry, poles, websocket. JWT auth +
   role-based access (citizen / operator / police / admin) + audit log.

5. **Command Dashboard** (`frontend/`)
   React 18 + TypeScript + Vite + Tailwind. Pages: Overview, Live
   Surveillance, Map & Heatmap (Leaflet + dark Carto tiles), Dispatch panel,
   System Telemetry. Live updates via WebSocket subscription.

6. **Citizen Safety App** (`frontend/src/pages/CitizenPage.tsx`)
   PWA-installable route at `/citizen` with one-tap SOS, geolocation, optional
   note, nearby safe spots.

7. **Live Incident Simulation Engine** (`backend/simulations/`)
   Replayable scenarios injected via `/api/simulation/inject{,-public}` —
   each scenario synthesises evidence and pushes through the same fusion
   pipeline as live sensors.

## Data flow (happy path)

```
sensor.read → ai.infer → fusion.fuse → DB(Incident)
   → AlertManager.generate → DB(Alert)
   → DispatchRecommender → bus.publish(incident.created, alert.created)
   → WebSocket hub fans out to dashboard
   → Operator dispatches a unit (DB(DispatchAssignment), bus.publish)
   → Status transitions: dispatched → en_route → on_scene → cleared
   → Incident.status = resolved, audit log entry
```

## Security

- JWT bearer auth (`HS256`, 24h expiry by default).
- Role-based gating on dispatch / simulation / status mutations.
- Audit log entries on all state mutations.
- CORS restricted to dashboard / citizen origins.
- "Edge-first" posture: only fused threats above the alert threshold are
  persisted and broadcast; raw sensor readings stay in process.

## Future hardware migration

- Raspberry Pi: `apt install python3.12 python3-venv libatlas-base-dev`,
  `pip install -e backend`, swap `CameraSensor.read` for a `picamera2` driver.
- Jetson Nano/Orin: install ultralytics + torch with CUDA wheels, set
  `ENABLE_YOLO=true`, point `CameraSensor` at a CSI/USB stream.
- LoRa pole comms: implement a `Sensor` subclass that exchanges sensor
  packets over LoRaWAN and forwards them to the same event bus.
