interface Props {
  severity: "low" | "medium" | "high" | "critical" | string;
}

const CLASS: Record<string, string> = {
  critical: "badge-critical",
  high: "badge-high",
  medium: "badge-medium",
  low: "badge-low",
};

export default function SeverityBadge({ severity }: Props) {
  return <span className={`badge ${CLASS[severity] ?? "badge-low"}`}>{severity.toUpperCase()}</span>;
}
