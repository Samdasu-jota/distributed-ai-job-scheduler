/**
 * WebSocket hook for real-time dashboard metrics (queue depths, worker counts).
 */

import { useEffect, useRef, useState, useCallback } from "react";

export interface DashboardUpdate {
  queues: Record<string, number>;
  workers: Record<string, number>;
  active_jobs: number;
  pending_jobs: number;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const MAX_BACKOFF_MS = 30_000;

export function useDashboard() {
  const [data, setData] = useState<DashboardUpdate | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    const ws = new WebSocket(`${WS_URL}/api/jobs/ws/dashboard`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      backoffRef.current = 1000;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "dashboard_update") {
          setData(msg.data as DashboardUpdate);
        }
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (mountedRef.current) {
        const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
        backoffRef.current = delay * 2;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, connected };
}
