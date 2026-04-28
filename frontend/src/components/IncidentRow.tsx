import { Incident } from "../api";
import SeverityBadge from "./SeverityBadge";

interface Props {
  incident: Incident;
  onClick?: () => void;
  selected?: boolean;
}

export default function IncidentRow({ incident, onClick, selected }: Props) {
  const created = new Date(incident.created_at);
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg border transition-colors ${
        selected
          ? "border-suraksha-500 bg-suraksha-600/10"
          : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={incident.severity} />
          <span className="text-sm font-medium capitalize">{incident.type.replace(/_/g, " ")}</span>
        </div>
        <span className="text-xs text-slate-400">#{incident.id}</span>
      </div>
      <div className="text-xs text-slate-400 flex items-center justify-between">
        <span>
          score <span className="text-slate-200">{incident.score.toFixed(2)}</span> · {incident.pole_id ?? "n/a"}
        </span>
        <span>{created.toLocaleTimeString()}</span>
      </div>
      <div className="text-xs text-slate-500 mt-1 capitalize">status: {incident.status}</div>
    </button>
  );
}
