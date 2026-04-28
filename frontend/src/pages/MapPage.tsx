import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Marker, Popup, Rectangle, TileLayer } from "react-leaflet";
import L from "leaflet";
import { HeatmapCell, Pole, RiskZone, api } from "../api";
import { useDashboardStore } from "../store";

const DEFAULT_CENTER: [number, number] = [17.4426, 78.4071];
const GRID_RES = 0.005;

const poleIcon = L.divIcon({
  className: "",
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#0ea5e9;border:2px solid #f8fafc;box-shadow:0 0 8px #0ea5e9"></div>',
  iconSize: [14, 14],
});

export default function MapPage() {
  const [poles, setPoles] = useState<Pole[]>([]);
  const [cells, setCells] = useState<HeatmapCell[]>([]);
  const [zones, setZones] = useState<RiskZone[]>([]);
  const [patrol, setPatrol] = useState<Array<Record<string, unknown>>>([]);
  const incidents = useDashboardStore((s) => s.incidents);

  async function refresh() {
    const [pp, hm, rz, pp2] = await Promise.all([
      api.listPoles().catch(() => []),
      api.heatmap().catch(() => ({ cells: [], count: 0 })),
      api.riskZones().catch(() => ({ zones: [] })),
      api.patrolPlan().catch(() => ({ plan: [] })),
    ]);
    setPoles(pp);
    setCells(hm.cells);
    setZones(rz.zones);
    setPatrol(pp2.plan);
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  const recentIncidents = useMemo(
    () => incidents.filter((i) => i.latitude !== null && i.longitude !== null).slice(0, 50),
    [incidents]
  );

  return (
    <div className="grid grid-cols-12 gap-4 h-[80vh]">
      <div className="col-span-12 lg:col-span-9 panel p-0 overflow-hidden">
        <MapContainer center={DEFAULT_CENTER} zoom={12} className="h-full w-full">
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
          />
          {cells.map((c, i) => (
            <Rectangle
              key={i}
              bounds={[
                [c.lat - GRID_RES / 2, c.lon - GRID_RES / 2],
                [c.lat + GRID_RES / 2, c.lon + GRID_RES / 2],
              ]}
              pathOptions={{
                color: riskColor(c.risk),
                fillColor: riskColor(c.risk),
                fillOpacity: 0.35 + c.risk * 0.45,
                weight: 0,
              }}
            />
          ))}
          {poles.map((p) => (
            <Marker key={p.id} position={[p.lat, p.lon]} icon={poleIcon}>
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{p.name}</div>
                  <div>{p.id}</div>
                  <div>zone: {p.zone}</div>
                </div>
              </Popup>
            </Marker>
          ))}
          {recentIncidents.map((i) => (
            <CircleMarker
              key={i.id}
              center={[i.latitude!, i.longitude!]}
              radius={6 + i.score * 12}
              pathOptions={{
                color: severityColor(i.severity),
                fillColor: severityColor(i.severity),
                fillOpacity: 0.6,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold capitalize">{i.type.replace(/_/g, " ")}</div>
                  <div>severity: {i.severity}</div>
                  <div>score: {i.score.toFixed(2)}</div>
                  <div>status: {i.status}</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <aside className="col-span-12 lg:col-span-3 grid gap-3">
        <div className="panel">
          <h2 className="panel-title">Top Risk Zones</h2>
          <ol className="space-y-1">
            {zones.length === 0 && <div className="text-xs text-slate-500">no incidents indexed yet</div>}
            {zones.map((z) => (
              <li key={z.rank} className="flex items-center justify-between text-xs">
                <span>
                  #{z.rank} ({z.lat.toFixed(3)}, {z.lon.toFixed(3)})
                </span>
                <span style={{ color: riskColor(z.risk) }}>{(z.risk * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="panel">
          <h2 className="panel-title">Patrol Plan</h2>
          {patrol.length === 0 && <div className="text-xs text-slate-500">awaiting incidents…</div>}
          {patrol.map((p, i) => (
            <div key={i} className="text-xs text-slate-300">
              {p.step === "summary" ? (
                <div className="mt-1 pt-1 border-t border-slate-800 text-slate-400">
                  total: {(p.total_km as number)?.toFixed?.(2)} km · ~{p.estimated_minutes as number}m
                </div>
              ) : (
                <div>
                  step {p.step as number}: ({(p.lat as number).toFixed(3)}, {(p.lon as number).toFixed(3)}) ·
                  risk {((p.risk as number) * 100).toFixed(0)}%
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="panel">
          <h2 className="panel-title">Legend</h2>
          <div className="text-xs space-y-1">
            <div className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ background: "#0ea5e9" }}
              />{" "}
              Smart pole
            </div>
            <div className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ background: severityColor("critical") }}
              />{" "}
              Critical incident
            </div>
            <div className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ background: riskColor(0.9) }}
              />{" "}
              High-risk zone
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function riskColor(r: number): string {
  if (r > 0.75) return "#ef4444";
  if (r > 0.5) return "#f97316";
  if (r > 0.25) return "#eab308";
  return "#22c55e";
}

function severityColor(s: string): string {
  return (
    {
      critical: "#ef4444",
      high: "#f97316",
      medium: "#eab308",
      low: "#22c55e",
    } as Record<string, string>
  )[s] ?? "#94a3b8";
}
