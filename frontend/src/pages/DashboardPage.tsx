import { useEffect, useState } from "react";
import { useDashboardStore } from "../store";
import { api, Scenario } from "../api";
import IncidentRow from "../components/IncidentRow";

export default function DashboardPage() {
  const incidents = useDashboardStore((s) => s.incidents);
  const metrics = useDashboardStore((s) => s.metrics);
  const log = useDashboardStore((s) => s.log);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.scenarios().then(setScenarios).catch(() => undefined);
  }, []);

  async function inject(s: string) {
    setBusy(s);
    try {
      await api.injectScenario(s);
    } catch {
      try {
        await api.injectScenarioPublic(s);
      } catch {
        // ignore
      }
    } finally {
      setBusy(null);
    }
  }

  const cards = metrics
    ? [
        { label: "Active Poles", value: metrics.active_poles },
        { label: "Open Incidents", value: metrics.incidents_open },
        { label: "Total Alerts", value: metrics.alerts_total },
        { label: "Avg Latency", value: `${metrics.avg_latency_ms.toFixed(0)} ms` },
        { label: "P95 Latency", value: `${metrics.p95_latency_ms.toFixed(0)} ms` },
        {
          label: "Detection Acc",
          value: `${(metrics.detection_accuracy_target * 100).toFixed(0)}%`,
        },
        {
          label: "False Pos Rate",
          value: `${(metrics.false_positive_rate * 100).toFixed(1)}%`,
        },
        { label: "Total Incidents", value: metrics.incidents_total },
      ]
    : [];

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-12 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        {cards.map((c) => (
          <div key={c.label} className="panel">
            <div className="text-xs uppercase tracking-wider text-slate-400">{c.label}</div>
            <div className="text-2xl font-bold mt-1 font-mono">{c.value}</div>
          </div>
        ))}
      </div>

      <section className="col-span-12 lg:col-span-7 panel">
        <div className="flex items-center justify-between mb-3">
          <h2 className="panel-title m-0">Recent Incidents</h2>
          <span className="text-xs text-slate-400">{incidents.length} shown</span>
        </div>
        <div className="space-y-2 max-h-[60vh] overflow-y-auto">
          {incidents.length === 0 ? (
            <div className="text-sm text-slate-500">
              No incidents yet — inject a scenario or wait for the live simulation tick.
            </div>
          ) : (
            incidents.map((i) => <IncidentRow key={i.id} incident={i} />)
          )}
        </div>
      </section>

      <section className="col-span-12 lg:col-span-5 grid gap-4">
        <div className="panel">
          <h2 className="panel-title">Scenario Injector</h2>
          <div className="grid grid-cols-2 gap-2">
            {scenarios.map((s) => (
              <button
                key={s.id}
                onClick={() => inject(s.id)}
                disabled={busy === s.id}
                className="btn btn-ghost text-xs text-left"
              >
                {s.title}
              </button>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2 className="panel-title">Event Log</h2>
          <div className="font-mono text-xs space-y-1 max-h-[40vh] overflow-y-auto">
            {log.length === 0 && <div className="text-slate-500">no events yet…</div>}
            {log.map((line, i) => (
              <div key={i} className="text-slate-300 whitespace-pre-wrap">
                {line}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
