import { useEffect, useRef } from "react";
import { WS_URL, api } from "./api";
import { useDashboardStore } from "./store";

interface BusMessage {
  topic: string;
  [k: string]: unknown;
}

export function useLiveSocket() {
  const upsertIncident = useDashboardStore((s) => s.upsertIncident);
  const setIncidents = useDashboardStore((s) => s.setIncidents);
  const setMetrics = useDashboardStore((s) => s.setMetrics);
  const recordInference = useDashboardStore((s) => s.recordInference);
  const recordTelemetry = useDashboardStore((s) => s.recordTelemetry);
  const pushLog = useDashboardStore((s) => s.pushLog);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    async function bootstrap() {
      try {
        const [incidents, metrics] = await Promise.all([api.listIncidents({ limit: 50 }), api.metrics()]);
        if (!cancelled) {
          setIncidents(incidents);
          setMetrics(metrics);
        }
      } catch {
        // backend may still be coming up; bus subscription handles incremental
      }
    }

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => pushLog("WebSocket connected");
      ws.onclose = () => {
        pushLog("WebSocket disconnected, reconnecting…");
        if (!cancelled) reconnectTimer = setTimeout(connect, 2000);
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as BusMessage;
          switch (msg.topic) {
            case "incident.created": {
              const incident = (msg as unknown as { incident: Parameters<typeof upsertIncident>[0] }).incident;
              if (incident) {
                upsertIncident(incident);
                pushLog(
                  `🚨 [${incident.severity.toUpperCase()}] ${incident.type} score=${incident.score} pole=${incident.pole_id ?? "n/a"}`
                );
              }
              break;
            }
            case "alert.created":
              pushLog(`📣 alert created for incident ${msg["incident_id"]}`);
              break;
            case "dispatch.assigned":
              pushLog(
                `🚓 unit ${msg["unit_id"]} dispatched to incident ${msg["incident_id"]} (ETA ${msg["eta_seconds"]}s)`
              );
              break;
            case "dispatch.updated":
              pushLog(`🚓 assignment ${msg["assignment_id"]} -> ${msg["status"]}`);
              break;
            case "simulation.injected":
              pushLog(`🎬 scenario injected: ${msg["scenario"]}`);
              break;
            case "inference":
              recordInference(msg as never);
              break;
            case "telemetry":
              recordTelemetry(msg as never);
              break;
            default:
              break;
          }
        } catch (err) {
          // ignore non-json
        }
      };
    }

    bootstrap();
    connect();

    const metricsTimer = setInterval(async () => {
      try {
        const m = await api.metrics();
        setMetrics(m);
      } catch {
        // ignore
      }
    }, 4000);

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearInterval(metricsTimer);
      wsRef.current?.close();
    };
  }, [pushLog, recordInference, recordTelemetry, setIncidents, setMetrics, upsertIncident]);
}
