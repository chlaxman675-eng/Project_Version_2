import { create } from "zustand";
import { Incident, MetricsResponse } from "./api";

export interface InferenceFrame {
  pole_id: string;
  vision: Array<{ label: string; confidence: number }>;
  audio: Array<{ label: string; confidence: number }>;
  scene: { scene_label?: string; people_count?: number; motion_intensity?: number };
  timestamp: string;
}

export interface TelemetryFrame {
  pole_id: string;
  data: {
    battery_pct: number;
    cpu_temp_c: number;
    network_latency_ms: number;
    solar_input_w: number;
  };
  timestamp: string;
}

interface State {
  incidents: Incident[];
  metrics: MetricsResponse | null;
  inferenceByPole: Record<string, InferenceFrame>;
  telemetryByPole: Record<string, TelemetryFrame>;
  log: string[];
  pushLog: (line: string) => void;
  setIncidents: (i: Incident[]) => void;
  upsertIncident: (i: Incident) => void;
  setMetrics: (m: MetricsResponse) => void;
  recordInference: (f: InferenceFrame) => void;
  recordTelemetry: (f: TelemetryFrame) => void;
}

export const useDashboardStore = create<State>((set) => ({
  incidents: [],
  metrics: null,
  inferenceByPole: {},
  telemetryByPole: {},
  log: [],
  pushLog: (line) =>
    set((s) => ({ log: [`${new Date().toLocaleTimeString()}  ${line}`, ...s.log].slice(0, 200) })),
  setIncidents: (incidents) => set({ incidents }),
  upsertIncident: (i) =>
    set((s) => {
      const without = s.incidents.filter((x) => x.id !== i.id);
      return { incidents: [i, ...without].slice(0, 200) };
    }),
  setMetrics: (metrics) => set({ metrics }),
  recordInference: (f) =>
    set((s) => ({ inferenceByPole: { ...s.inferenceByPole, [f.pole_id]: f } })),
  recordTelemetry: (f) =>
    set((s) => ({ telemetryByPole: { ...s.telemetryByPole, [f.pole_id]: f } })),
}));
