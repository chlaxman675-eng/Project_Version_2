import { useEffect, useState } from "react";
import { Assignment, Incident, Unit, api } from "../api";
import IncidentRow from "../components/IncidentRow";
import { useDashboardStore } from "../store";

export default function DispatchPage() {
  const incidents = useDashboardStore((s) => s.incidents);
  const [units, setUnits] = useState<Unit[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const [u, a] = await Promise.all([api.listUnits(), api.listAssignments()]);
      setUnits(u);
      setAssignments(a);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  async function assign(unitId: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.assign(selected.id, unitId, "dispatched from console");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function progress(a: Assignment) {
    const next: Record<string, string> = {
      dispatched: "en_route",
      en_route: "on_scene",
      on_scene: "cleared",
      cleared: "cleared",
    };
    setBusy(true);
    try {
      await api.updateAssignment(a.id, next[a.status]);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const open = incidents.filter((i) => i.status === "open" || i.status === "dispatched");

  return (
    <div className="grid grid-cols-12 gap-4">
      <section className="col-span-12 md:col-span-4 panel">
        <h2 className="panel-title">Incoming Alerts</h2>
        <div className="space-y-2 max-h-[70vh] overflow-y-auto">
          {open.length === 0 && (
            <div className="text-xs text-slate-500">no open incidents — system is calm.</div>
          )}
          {open.map((i) => (
            <IncidentRow
              key={i.id}
              incident={i}
              selected={selected?.id === i.id}
              onClick={() => setSelected(i)}
            />
          ))}
        </div>
      </section>

      <section className="col-span-12 md:col-span-4 panel">
        <h2 className="panel-title">Unit Selection</h2>
        {!selected && <div className="text-xs text-slate-500">select an incident</div>}
        {selected && (
          <div className="space-y-2">
            <div className="text-sm">
              <span className="text-slate-400">Incident #{selected.id}</span> ·{" "}
              <span className="capitalize">{selected.type.replace(/_/g, " ")}</span>
            </div>
            <div className="text-xs text-slate-500 mb-2">
              {selected.latitude?.toFixed(4)}, {selected.longitude?.toFixed(4)}
            </div>
            {error && <div className="text-xs text-red-400">{error}</div>}
            <ul className="space-y-1">
              {units.map((u) => (
                <li
                  key={u.unit_id}
                  className="flex items-center justify-between border border-slate-800 rounded px-2 py-1.5"
                >
                  <div>
                    <div className="text-sm">{u.unit_id}</div>
                    <div className="text-[11px] text-slate-400">{u.kind}</div>
                  </div>
                  <button
                    className="btn btn-primary text-xs"
                    disabled={busy || !u.available}
                    onClick={() => assign(u.unit_id)}
                  >
                    Dispatch
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="col-span-12 md:col-span-4 panel">
        <h2 className="panel-title">Active Assignments</h2>
        <div className="space-y-2 max-h-[70vh] overflow-y-auto">
          {assignments.length === 0 && (
            <div className="text-xs text-slate-500">no assignments yet</div>
          )}
          {assignments.map((a) => (
            <div key={a.id} className="border border-slate-800 rounded p-2">
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  {a.unit_id} → #{a.incident_id}
                </div>
                <span className="badge badge-low">{a.status}</span>
              </div>
              <div className="text-[11px] text-slate-500">ETA {Math.max(0, a.eta_seconds)}s</div>
              <button
                onClick={() => progress(a)}
                disabled={busy || a.status === "cleared"}
                className="btn btn-ghost text-xs mt-2"
              >
                Advance →
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
