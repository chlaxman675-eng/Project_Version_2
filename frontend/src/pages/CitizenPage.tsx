import { useEffect, useState } from "react";
import { api } from "../api";

export default function CitizenPage() {
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [safe, setSafe] = useState<{ poles: Array<{ id: string; name: string }>; lowRisk: number }>({
    poles: [],
    lowRisk: 0,
  });

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => setCoords({ lat: 17.4486, lon: 78.3908 }),
        { timeout: 5000 }
      );
    } else {
      setCoords({ lat: 17.4486, lon: 78.3908 });
    }
    fetch("/api/citizen/safe-zones")
      .then((r) => r.json())
      .then((d) => setSafe({ poles: d.poles ?? [], lowRisk: (d.low_risk_areas ?? []).length }))
      .catch(() => undefined);
  }, []);

  async function fireSos() {
    if (!coords) return;
    setSending(true);
    setConfirmation(null);
    try {
      const r = await api.sosAnonymous(coords.lat, coords.lon, note || "Citizen panic SOS");
      setConfirmation(`SOS dispatched. Reference #${r.report_id}. Stay safe — units are responding.`);
    } catch (err) {
      setConfirmation(`Failed to send SOS: ${(err as Error).message}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-screen p-6 max-w-md mx-auto flex flex-col gap-4">
      <header className="flex items-center gap-3">
        <img src="/shield.svg" className="w-10 h-10" alt="" />
        <div>
          <div className="text-xl font-bold">SurakshaNet — Citizen Safety</div>
          <div className="text-xs text-slate-400">Tap once. Help is on the way.</div>
        </div>
      </header>

      <div className="panel text-center py-10">
        <button
          onClick={fireSos}
          disabled={sending || !coords}
          className="relative mx-auto w-44 h-44 rounded-full bg-red-600 hover:bg-red-500 active:scale-95 transition shadow-2xl"
          aria-label="Trigger SOS"
        >
          <span className="absolute inset-0 rounded-full bg-red-500 animate-pulseRing opacity-60" />
          <span className="relative text-white text-3xl font-bold tracking-wider">SOS</span>
        </button>
        <div className="text-xs text-slate-400 mt-3">
          {coords ? `📍 ${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}` : "locating…"}
        </div>
      </div>

      <div className="panel">
        <label className="text-xs uppercase text-slate-400">Optional note</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className="w-full mt-1 bg-slate-950 border border-slate-700 rounded p-2 text-sm"
          placeholder="What's happening? (optional)"
        />
      </div>

      {confirmation && (
        <div className="panel text-sm bg-emerald-900/30 border-emerald-700">{confirmation}</div>
      )}

      <div className="panel">
        <h2 className="panel-title">Nearby Safe Spots</h2>
        <div className="text-xs text-slate-400 mb-2">{safe.lowRisk} low-risk areas indexed</div>
        <ul className="space-y-1 text-sm">
          {safe.poles.slice(0, 5).map((p) => (
            <li key={p.id} className="flex items-center justify-between">
              <span>{p.name}</span>
              <span className="text-emerald-400 text-xs">monitored</span>
            </li>
          ))}
        </ul>
      </div>

      <a className="text-center text-xs text-slate-500 hover:text-slate-300" href="/login">
        ← Operator console
      </a>
    </div>
  );
}
