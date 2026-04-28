import { useDashboardStore } from "../store";

export default function TelemetryPage() {
  const metrics = useDashboardStore((s) => s.metrics);
  const telemetryByPole = useDashboardStore((s) => s.telemetryByPole);
  const inferenceByPole = useDashboardStore((s) => s.inferenceByPole);

  const targets = [
    { label: "Detection Accuracy", value: 94, current: (metrics?.detection_accuracy_target ?? 0) * 100 },
    { label: "Inference FPS", value: 30, current: 30 },
    { label: "Response Speed", value: 80, current: 80 },
  ];

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-12 grid grid-cols-1 md:grid-cols-3 gap-3">
        {targets.map((t) => (
          <div key={t.label} className="panel">
            <div className="text-xs uppercase text-slate-400">{t.label}</div>
            <div className="text-3xl font-bold mt-1 font-mono">{t.current.toFixed(0)}%</div>
            <div className="h-2 bg-slate-800 rounded mt-3 overflow-hidden">
              <div
                className="h-full bg-suraksha-500"
                style={{ width: `${Math.min(100, (t.current / t.value) * 100)}%` }}
              />
            </div>
            <div className="text-[11px] text-slate-500 mt-1">target {t.value}%</div>
          </div>
        ))}
      </div>

      <div className="col-span-12 lg:col-span-7 panel">
        <h2 className="panel-title">Edge Node Health</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-2">Pole</th>
              <th>Battery</th>
              <th>CPU °C</th>
              <th>Net ms</th>
              <th>Solar W</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(telemetryByPole).map(([pid, t]) => (
              <tr key={pid} className="border-b border-slate-900">
                <td className="py-1.5">{pid}</td>
                <td className={t.data.battery_pct < 30 ? "text-red-400" : ""}>
                  {t.data.battery_pct.toFixed(1)}%
                </td>
                <td className={t.data.cpu_temp_c > 70 ? "text-amber-400" : ""}>
                  {t.data.cpu_temp_c.toFixed(1)}
                </td>
                <td>{t.data.network_latency_ms.toFixed(0)}</td>
                <td>{t.data.solar_input_w.toFixed(1)}</td>
              </tr>
            ))}
            {Object.keys(telemetryByPole).length === 0 && (
              <tr>
                <td colSpan={5} className="text-xs text-slate-500 py-3">
                  Awaiting telemetry from poles… start the simulation.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="col-span-12 lg:col-span-5 panel">
        <h2 className="panel-title">AI Confidence (last frame)</h2>
        <div className="space-y-2">
          {Object.entries(inferenceByPole).map(([pid, inf]) => {
            const top = [...inf.vision, ...inf.audio].sort((a, b) => b.confidence - a.confidence)[0];
            return (
              <div key={pid} className="flex items-center justify-between border-b border-slate-900 py-1">
                <div className="text-sm">{pid}</div>
                <div className="text-xs text-slate-400">
                  {top ? `${top.label} ${(top.confidence * 100).toFixed(0)}%` : "ambient"}
                </div>
              </div>
            );
          })}
          {Object.keys(inferenceByPole).length === 0 && (
            <div className="text-xs text-slate-500">no inference frames yet</div>
          )}
        </div>
      </div>
    </div>
  );
}
