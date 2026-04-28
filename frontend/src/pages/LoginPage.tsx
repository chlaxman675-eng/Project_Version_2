import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const PRESETS = [
  { label: "Admin", email: "admin@suraksha.local", password: "SurakshaAdmin123!" },
  { label: "Operator", email: "operator@suraksha.local", password: "Operator123!" },
  { label: "Police", email: "officer@suraksha.local", password: "Police123!" },
  { label: "Citizen", email: "citizen@suraksha.local", password: "Citizen123!" },
];

export default function LoginPage() {
  const [email, setEmail] = useState("admin@suraksha.local");
  const [password, setPassword] = useState("SurakshaAdmin123!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const r = await api.login(email, password);
      localStorage.setItem("auth_token", r.access_token);
      localStorage.setItem("auth_role", r.role);
      localStorage.setItem("auth_email", r.email);
      navigate("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <div className="panel max-w-md w-full">
        <div className="flex items-center gap-3 mb-6">
          <img src="/shield.svg" alt="" className="w-10 h-10" />
          <div>
            <div className="text-xl font-bold">SurakshaNet AI</div>
            <div className="text-xs uppercase tracking-widest text-slate-400">Command Center</div>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="text-xs uppercase text-slate-400">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full mt-1 bg-slate-950 border border-slate-700 rounded-md px-3 py-2"
              required
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase text-slate-400">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full mt-1 bg-slate-950 border border-slate-700 rounded-md px-3 py-2"
              required
            />
          </label>
          {error && <div className="text-red-400 text-sm">{error}</div>}
          <button className="btn btn-primary w-full" disabled={loading}>
            {loading ? "Authenticating..." : "Sign in"}
          </button>
        </form>
        <div className="mt-6">
          <div className="text-xs uppercase text-slate-400 mb-2">Demo accounts</div>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => {
                  setEmail(p.email);
                  setPassword(p.password);
                }}
                className="btn btn-ghost text-xs"
                type="button"
              >
                {p.label}
              </button>
            ))}
          </div>
          <a href="/citizen" className="block text-center text-xs text-slate-400 mt-4 hover:text-slate-200">
            → Open citizen safety app
          </a>
        </div>
      </div>
    </div>
  );
}
