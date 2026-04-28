import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useDashboardStore } from "./store";
import { useLiveSocket } from "./useLiveSocket";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/live", label: "Live Surveillance" },
  { to: "/map", label: "Map & Heatmap" },
  { to: "/dispatch", label: "Dispatch" },
  { to: "/telemetry", label: "Telemetry" },
];

export default function App() {
  useLiveSocket();
  const metrics = useDashboardStore((s) => s.metrics);
  const navigate = useNavigate();

  useEffect(() => {
    if (!localStorage.getItem("auth_token")) navigate("/login", { replace: true });
  }, [navigate]);

  const role = localStorage.getItem("auth_role") ?? "guest";
  const email = localStorage.getItem("auth_email") ?? "";

  function logout() {
    localStorage.clear();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-6 py-3 border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/shield.svg" alt="" className="w-8 h-8" />
          <div>
            <div className="text-lg font-bold tracking-tight">
              Suraksha<span className="text-suraksha-500">Net</span> AI
            </div>
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Smart Predictive Public Safety
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm border ${
                  isActive
                    ? "bg-suraksha-600/20 text-suraksha-50 border-suraksha-600/40"
                    : "border-transparent text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-pulseRing absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
            </span>
            <span className="text-emerald-400 font-medium">LIVE</span>
          </div>
          {metrics && (
            <span className="text-slate-400 hidden md:inline">
              {metrics.active_poles} poles · {metrics.incidents_open} open
            </span>
          )}
          <span className="text-slate-400 hidden md:inline">
            {email} <span className="text-slate-600">·</span> {role}
          </span>
          <button onClick={logout} className="btn btn-ghost text-xs">
            Logout
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
      <footer className="px-6 py-3 border-t border-slate-800 text-xs text-slate-500 flex justify-between">
        <span>v0.1.0 — local-first MVP</span>
        <span>Edge AI · IoT · Real-time response</span>
      </footer>
    </div>
  );
}
