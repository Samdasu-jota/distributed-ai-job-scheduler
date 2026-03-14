/**
 * WebSocket hook for real-time job updates.
 * Adapted from usePipelineAlerts.ts in Speech AI Pipeline Diagnostic.
 * Reconnects automatically with exponential backoff on disconnect.
 */

import { useEffect, useRef, useState, useCallback } from "react";

export interface TaskUpdate {
  task_id: string;
  stage_name: string;
  status: string;
  worker_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  retry_count: number;
  error: string | null;
}

export interface JobUpdate {
  job_id: string;
  status: string;
  tasks: TaskUpdate[];
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const MAX_BACKOFF_MS = 30_000;

export function useJobStream(jobId: string | null) {
  const [updates, setUpdates] = useState<JobUpdate[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!jobId || !mountedRef.current) return;

    const ws = new WebSocket(`${WS_URL}/api/jobs/ws/jobs/${jobId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      backoffRef.current = 1000;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "job_update") {
          setUpdates((prev) => [msg.data as JobUpdate, ...prev].slice(0, 100));
        }
      } catch {
        // ignore malformed messages
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
  }, [jobId]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { updates, connected };
}
