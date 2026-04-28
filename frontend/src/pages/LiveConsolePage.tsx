import { useEffect, useState } from "react";
import { Pole, api } from "../api";
import { useDashboardStore } from "../store";

export default function LiveConsolePage() {
  const [poles, setPoles] = useState<Pole[]>([]);
  const inferenceByPole = useDashboardStore((s) => s.inferenceByPole);
  const telemetryByPole = useDashboardStore((s) => s.telemetryByPole);
  const incidents = useDashboardStore((s) => s.incidents);

  useEffect(() => {
    api.listPoles().then(setPoles).catch(() => undefined);
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {poles.map((p) => {
        const inf = inferenceByPole[p.id];
        const tel = telemetryByPole[p.id];
        const recent = incidents.filter((i) => i.pole_id === p.id).slice(0, 3);
        const sceneLabel = inf?.scene?.scene_label ?? "calm_street";
        const motion = (inf?.scene?.motion_intensity ?? 0) * 100;
        return (
          <div key={p.id} className="panel">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-sm font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400">
                  {p.id} · {p.zone}
                </div>
              </div>
              <span
                className={`badge ${
                  p.status === "online" ? "bg-emerald-600/20 text-emerald-300" : "badge-low"
                }`}
              >
                {p.status}
              </span>
            </div>
            <div
              className="aspect-video rounded-md border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 grid place-items-center text-center mb-3 relative overflow-hidden"
              style={{ backgroundImage: gradientFor(sceneLabel) }}
            >
              <div className="absolute inset-2 border border-slate-700/50 rounded" />
              <div className="text-xs uppercase tracking-widest text-slate-300">
                {sceneLabel.replace(/_/g, " ")}
              </div>
              <div className="absolute top-2 left-2 text-[10px] font-mono text-slate-300">
                CAM · 1280×720 · 30fps
              </div>
              <div className="absolute bottom-2 left-2 text-[10px] font-mono text-slate-300">
                people: {inf?.scene?.people_count ?? 0}
              </div>
              {inf?.vision?.length ? (
                <div className="absolute bottom-2 right-2 text-[10px] font-mono px-1.5 py-0.5 bg-red-600/40 border border-red-500 rounded">
                  AI: {inf.vision.map((v) => `${v.label} ${(v.confidence * 100).toFixed(0)}%`).join(", ")}
                </div>
              ) : null}
            </div>
            <div className="text-xs text-slate-400">
              <div>Motion: {motion.toFixed(0)}%</div>
              {inf?.audio?.length ? (
                <div className="text-amber-400">
                  Audio: {inf.audio.map((a) => `${a.label} ${(a.confidence * 100).toFixed(0)}%`).join(", ")}
                </div>
              ) : null}
              {tel && (
                <div className="mt-1 grid grid-cols-3 gap-1 text-[11px] text-slate-300">
                  <span>🔋 {tel.data.battery_pct.toFixed(0)}%</span>
                  <span>🌡 {tel.data.cpu_temp_c.toFixed(0)}°C</span>
                  <span>📶 {tel.data.network_latency_ms.toFixed(0)}ms</span>
                </div>
              )}
            </div>
            {recent.length > 0 && (
              <div className="mt-3 border-t border-slate-800 pt-2">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Recent</div>
                {recent.map((i) => (
                  <div key={i.id} className="text-xs text-slate-300 flex items-center gap-2">
                    <span className={`badge badge-${i.severity}`}>{i.severity}</span>
                    <span className="capitalize">{i.type.replace(/_/g, " ")}</span>
                    <span className="text-slate-500 ml-auto">{i.score.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function gradientFor(scene: string): string {
  const palette: Record<string, string> = {
    calm_street: "linear-gradient(135deg, #0f172a, #1e293b)",
    busy_intersection: "linear-gradient(135deg, #1e3a8a, #0f172a)",
    loitering: "linear-gradient(135deg, #422006, #1e293b)",
    abandoned_object: "linear-gradient(135deg, #4c1d95, #1e293b)",
    fight: "linear-gradient(135deg, #7f1d1d, #1f2937)",
    intrusion: "linear-gradient(135deg, #b45309, #1f2937)",
    crowd_anomaly: "linear-gradient(135deg, #be185d, #1e293b)",
  };
  return palette[scene] ?? palette["calm_street"];
}
