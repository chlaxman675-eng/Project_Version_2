const API_BASE = import.meta.env.VITE_API_BASE || "/api";

export interface Incident {
  id: number;
  pole_id: string | null;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  score: number;
  status: "open" | "dispatched" | "resolved" | "false_positive";
  description: string;
  latitude: number | null;
  longitude: number | null;
  sources: Record<string, number>;
  created_at: string;
  resolved_at: string | null;
}

export interface Pole {
  id: string;
  name: string;
  lat: number;
  lon: number;
  zone: string;
  status: string;
  last_seen?: string;
}

export interface Unit {
  unit_id: string;
  kind: string;
  lat: number;
  lon: number;
  available: boolean;
}

export interface Assignment {
  id: number;
  incident_id: number;
  unit_id: string;
  status: string;
  eta_seconds: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface MetricsResponse {
  total_detections: number;
  total_alerts: number;
  total_false_positives: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  detection_accuracy_target: number;
  false_positive_rate: number;
  active_poles: number;
  incidents_total: number;
  incidents_open: number;
  alerts_total: number;
  poles_total: number;
  timestamp: string;
}

export interface HeatmapCell {
  lat: number;
  lon: number;
  risk: number;
  incident_count: number;
}

export interface RiskZone extends HeatmapCell {
  rank: number;
}

export interface Scenario {
  id: string;
  title: string;
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("auth_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/auth/login`, { method: "POST", body });
    if (!res.ok) throw new Error("invalid credentials");
    return (await res.json()) as { access_token: string; role: string; email: string };
  },
  me: () => request<{ id: number; email: string; full_name: string; role: string }>("/auth/me"),
  listIncidents: (params?: { status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString() ? `?${search.toString()}` : "";
    return request<Incident[]>(`/incidents${qs}`);
  },
  updateIncidentStatus: (id: number, status: string) =>
    request<Incident>(`/incidents/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  listPoles: () => request<Pole[]>("/poles"),
  listUnits: () => request<Unit[]>("/dispatch/units"),
  listAssignments: () => request<Assignment[]>("/dispatch/assignments"),
  assign: (incident_id: number, unit_id: string, notes = "") =>
    request<Assignment>("/dispatch/assign", {
      method: "POST",
      body: JSON.stringify({ incident_id, unit_id, notes }),
    }),
  updateAssignment: (id: number, status: string) =>
    request<Assignment>(`/dispatch/assignments/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  metrics: () => request<MetricsResponse>("/telemetry/metrics"),
  heatmap: () => request<{ cells: HeatmapCell[]; count: number }>("/prediction/heatmap"),
  riskZones: () => request<{ zones: RiskZone[] }>("/prediction/risk-zones"),
  patrolPlan: () =>
    request<{ plan: Array<Record<string, unknown>> }>("/prediction/patrol-recommendations"),
  scenarios: () => request<Scenario[]>("/simulation/scenarios"),
  injectScenario: (scenario: string, pole_id?: string) =>
    request<{ ok: boolean }>("/simulation/inject", {
      method: "POST",
      body: JSON.stringify({ scenario, pole_id }),
    }),
  injectScenarioPublic: (scenario: string, pole_id?: string) =>
    request<{ ok: boolean }>("/simulation/inject-public", {
      method: "POST",
      body: JSON.stringify({ scenario, pole_id }),
    }),
  startSim: () => request<{ running: boolean }>("/simulation/start", { method: "POST" }),
  stopSim: () => request<{ running: boolean }>("/simulation/stop", { method: "POST" }),
  sosAnonymous: (latitude: number | null, longitude: number | null, note?: string) =>
    request<{ ok: boolean; report_id: number }>("/citizen/sos/anonymous", {
      method: "POST",
      body: JSON.stringify({ latitude, longitude, note }),
    }),
};

export const WS_URL = (() => {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // dev: vite proxy doesn't proxy WS by default, hit backend directly
  const host =
    import.meta.env.VITE_WS_HOST ??
    (window.location.port === "5173" ? `${window.location.hostname}:8000` : window.location.host);
  return `${proto}//${host}/api/ws`;
})();
