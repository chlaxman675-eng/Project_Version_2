"""Crime risk prediction using historical incidents + temporal patterns.

Approach: Bin incidents into a lat/lon grid + hour-of-day, compute a
temporally-weighted risk per cell (recent events count more), normalise to
0..1, then derive zones and patrol routes.

Lightweight, dependency-free except numpy. Replaceable with PyTorch / GNN
forecasting later — the API contract stays the same.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident, Pole

GRID_RES = 0.005  # ~500m per cell at this latitude
DEFAULT_CENTER = (17.4426, 78.4071)  # Hyderabad-ish
DEFAULT_RADIUS_DEG = 0.10  # ~11km


@dataclass
class HeatmapCell:
    lat: float
    lon: float
    risk: float
    incident_count: int


class HeatmapEngine:
    """Recompute risk scores from the incidents table on demand."""

    def __init__(self, half_life_hours: float = 24.0) -> None:
        self.half_life = half_life_hours

    async def compute(
        self, session: AsyncSession,
        center: tuple[float, float] = DEFAULT_CENTER,
        radius_deg: float = DEFAULT_RADIUS_DEG,
    ) -> list[HeatmapCell]:
        rows = (await session.execute(select(Incident))).scalars().all()
        now = datetime.now(timezone.utc)
        # decay factor for incident weight: 0.5 ^ (age_hours / half_life)
        cells: dict[tuple[int, int], dict] = {}
        for inc in rows:
            if inc.latitude is None or inc.longitude is None:
                continue
            if abs(inc.latitude - center[0]) > radius_deg:
                continue
            if abs(inc.longitude - center[1]) > radius_deg:
                continue
            ix = int(round(inc.latitude / GRID_RES))
            iy = int(round(inc.longitude / GRID_RES))
            key = (ix, iy)
            created_at = inc.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_h = max(0.0, (now - created_at).total_seconds() / 3600)
            decay = 0.5 ** (age_h / self.half_life)
            severity_w = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.25}.get(inc.severity, 0.4)
            weight = severity_w * decay
            slot = cells.setdefault(key, {"lat": ix * GRID_RES, "lon": iy * GRID_RES,
                                          "risk_raw": 0.0, "count": 0})
            slot["risk_raw"] += weight
            slot["count"] += 1

        if not cells:
            return []
        max_risk = max(c["risk_raw"] for c in cells.values()) or 1.0
        return [
            HeatmapCell(
                lat=c["lat"], lon=c["lon"],
                risk=round(min(1.0, c["risk_raw"] / max_risk), 3),
                incident_count=c["count"],
            )
            for c in cells.values()
        ]

    async def risk_zones(self, session: AsyncSession, top_n: int = 5) -> list[dict]:
        cells = await self.compute(session)
        cells.sort(key=lambda c: c.risk, reverse=True)
        return [{"lat": c.lat, "lon": c.lon, "risk": c.risk,
                 "incident_count": c.incident_count, "rank": i + 1}
                for i, c in enumerate(cells[:top_n])]

    async def patrol_recommendations(self, session: AsyncSession) -> list[dict]:
        zones = await self.risk_zones(session, top_n=8)
        poles = (await session.execute(select(Pole))).scalars().all()
        # Greedy nearest-neighbour TSP from a notional precinct.
        if not zones:
            return []
        ordered = []
        remaining = zones[:]
        cur_lat, cur_lon = poles[0].latitude if poles else DEFAULT_CENTER[0], \
            poles[0].longitude if poles else DEFAULT_CENTER[1]
        while remaining:
            nxt = min(remaining, key=lambda z: (z["lat"] - cur_lat) ** 2 + (z["lon"] - cur_lon) ** 2)
            ordered.append(nxt)
            cur_lat, cur_lon = nxt["lat"], nxt["lon"]
            remaining.remove(nxt)
        # Compute total distance for the route summary.
        total_km = 0.0
        for a, b in zip(ordered, ordered[1:]):
            total_km += _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
        return [
            {
                "step": i + 1,
                "lat": z["lat"], "lon": z["lon"],
                "risk": z["risk"],
                "expected_dwell_minutes": int(10 + 20 * z["risk"]),
            }
            for i, z in enumerate(ordered)
        ] + [{"step": "summary", "total_km": round(total_km, 2),
              "estimated_minutes": int(total_km / 30 * 60) if total_km else 0}]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Lightweight smoothing helper for callers that want a 2D array view.
def cells_to_grid(cells: list[HeatmapCell]) -> np.ndarray:
    if not cells:
        return np.zeros((0, 0), dtype=float)
    lats = sorted({c.lat for c in cells})
    lons = sorted({c.lon for c in cells})
    grid = np.zeros((len(lats), len(lons)), dtype=float)
    lat_idx = {v: i for i, v in enumerate(lats)}
    lon_idx = {v: i for i, v in enumerate(lons)}
    for c in cells:
        grid[lat_idx[c.lat], lon_idx[c.lon]] = c.risk
    return grid


heatmap_engine = HeatmapEngine()
