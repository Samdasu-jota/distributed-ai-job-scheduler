"use client";

/**
 * WorkerStatusGrid — visual grid of all registered workers.
 * Reuses the PipelineHealthGrid visual pattern from Speech AI Pipeline Diagnostic.
 * IDLE=green, BUSY=yellow, DEAD=red — color-coded by status.
 */

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Worker {
  id: string;
  hostname: string;
  worker_type: string;
  status: string;
  tasks_completed: number;
  tasks_failed: number;
  last_heartbeat: string;
  current_task_id: string | null;
}

const STATUS_STYLES: Record<string, string> = {
  IDLE: "bg-green-50 border-green-300",
  BUSY: "bg-yellow-50 border-yellow-400",
  DEAD: "bg-red-50 border-red-400",
};

const STATUS_BADGE: Record<string, string> = {
  IDLE: "bg-green-100 text-green-800",
  BUSY: "bg-yellow-100 text-yellow-800",
  DEAD: "bg-red-100 text-red-800",
};

const STAGE_LABELS: Record<string, string> = {
  audio_preprocessing: "Audio",
  speech_to_text: "STT",
  nlp_processing: "NLP",
  grammar_correction: "Grammar",
  natural_phrasing: "Phrasing",
  diagnostics: "Diagnostics",
  aggregation: "Aggregation",
};

export function WorkerStatusGrid() {
  const [workers, setWorkers] = useState<Worker[]>([]);

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch(`${API_URL}/api/workers`);
        const data = await res.json();
        setWorkers(data.workers ?? []);
      } catch {
        // keep previous
      }
    };
    fetch_();
    const interval = setInterval(fetch_, 5000);
    return () => clearInterval(interval);
  }, []);

  const busyCount = workers.filter(w => w.status === "BUSY").length;
  const deadCount = workers.filter(w => w.status === "DEAD").length;

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-800">Workers</h2>
        <div className="flex gap-3 text-xs">
          <span className="text-green-700 font-medium">{workers.filter(w => w.status === "IDLE").length} idle</span>
          <span className="text-yellow-700 font-medium">{busyCount} busy</span>
          {deadCount > 0 && <span className="text-red-700 font-medium">{deadCount} dead</span>}
        </div>
      </div>

      {workers.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-6">No workers registered</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {workers.map((w) => (
            <div
              key={w.id}
              className={`border rounded-lg p-3 ${STATUS_STYLES[w.status] ?? "bg-gray-50 border-gray-200"}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-700">
                  {STAGE_LABELS[w.worker_type] ?? w.worker_type}
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_BADGE[w.status] ?? "bg-gray-100 text-gray-600"}`}>
                  {w.status}
                </span>
              </div>
              <p className="text-xs text-gray-500 font-mono truncate">{w.hostname.slice(0, 20)}</p>
              <div className="mt-1.5 flex gap-2 text-xs text-gray-500">
                <span>✓ {w.tasks_completed}</span>
                {w.tasks_failed > 0 && <span className="text-red-500">✗ {w.tasks_failed}</span>}
              </div>
              {w.current_task_id && (
                <p className="text-xs text-yellow-600 mt-1 font-mono truncate">
                  {w.current_task_id.slice(0, 8)}…
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
