"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function JobSubmitForm() {
  const [userId, setUserId] = useState("student-demo");
  const [priority, setPriority] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          duration_ms: 1000,
          priority,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLastJobId(data.job_id);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Submit Job</h2>
      <form onSubmit={handleSubmit} className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-600 mb-1">User ID</label>
          <input
            type="text"
            value={userId}
            onChange={e => setUserId(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">Priority (1=high, 10=low)</label>
          <input
            type="number"
            min={1}
            max={10}
            value={priority}
            onChange={e => setPriority(Number(e.target.value))}
            className="border rounded px-2 py-1.5 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {submitting ? "Submitting…" : "Submit Job"}
        </button>
        {lastJobId && (
          <div className="text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1">
            Submitted: <span className="font-mono">{lastJobId.slice(0, 8)}…</span>
          </div>
        )}
        {error && (
          <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
            {error}
          </div>
        )}
      </form>
    </div>
  );
}
