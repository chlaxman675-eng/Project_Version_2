"""Recommend response units for an incident.

Greedy nearest-unit policy with severity-aware unit selection. Replaceable
with an OR-tools or RL-based optimiser later.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.db.models import Incident


@dataclass
class ResponseUnit:
    unit_id: str
    kind: str  # patrol | swat | medic | drone
    latitude: float
    longitude: float
    available: bool = True


# Static demo fleet anchored around Hyderabad-like coordinates.
DEMO_UNITS: list[ResponseUnit] = [
    ResponseUnit("UNIT-A1", "patrol", 17.4500, 78.3900),
    ResponseUnit("UNIT-A2", "patrol", 17.4400, 78.3800),
    ResponseUnit("UNIT-S1", "swat", 17.4450, 78.3850),
    ResponseUnit("UNIT-M1", "medic", 17.4350, 78.4000),
    ResponseUnit("UNIT-D1", "drone", 17.4470, 78.3920),
    ResponseUnit("UNIT-B2", "patrol", 17.3700, 78.4750),
    ResponseUnit("UNIT-N1", "patrol", 17.4399, 78.4983),
]

# minimum unit kinds per severity.
SEVERITY_PROFILE = {
    "critical": ["swat", "patrol", "medic"],
    "high": ["patrol", "medic"],
    "medium": ["patrol"],
    "low": ["patrol"],
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class DispatchRecommender:
    def __init__(self, units: list[ResponseUnit] | None = None) -> None:
        self.units = units or DEMO_UNITS

    def recommend(self, incident: Incident) -> dict:
        target_kinds = SEVERITY_PROFILE.get(incident.severity, ["patrol"])
        chosen: list[dict] = []

        if incident.latitude is None or incident.longitude is None:
            # fallback: just pick first available of each kind
            for kind in target_kinds:
                u = next((u for u in self.units if u.kind == kind and u.available), None)
                if u:
                    chosen.append({"unit_id": u.unit_id, "kind": u.kind, "eta_seconds": 600})
            return {"units": chosen, "policy": "fallback"}

        for kind in target_kinds:
            candidates = [u for u in self.units if u.kind == kind and u.available]
            if not candidates:
                continue
            best = min(
                candidates,
                key=lambda u: _haversine_km(incident.latitude, incident.longitude, u.latitude, u.longitude),
            )
            distance_km = _haversine_km(incident.latitude, incident.longitude, best.latitude, best.longitude)
            # Assume ~40 km/h average urban response speed.
            eta_seconds = int((distance_km / 40.0) * 3600)
            chosen.append({
                "unit_id": best.unit_id, "kind": best.kind,
                "distance_km": round(distance_km, 3),
                "eta_seconds": max(60, eta_seconds),
            })
        return {"units": chosen, "policy": "nearest_by_kind"}
