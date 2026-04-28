"""HTTP API routers."""
from fastapi import APIRouter

from app.api import (
    alerts,
    auth,
    citizen,
    dispatch,
    incidents,
    poles,
    prediction,
    simulation,
    stream,
    telemetry,
    websocket,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(dispatch.router, prefix="/dispatch", tags=["dispatch"])
api_router.include_router(prediction.router, prefix="/prediction", tags=["prediction"])
api_router.include_router(citizen.router, prefix="/citizen", tags=["citizen"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(poles.router, prefix="/poles", tags=["poles"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
api_router.include_router(stream.router, tags=["stream"])
api_router.include_router(websocket.router, tags=["websocket"])
