"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useDashboard } from "@/hooks/useDashboard";

const STREAM_LABELS: Record<string, string> = {
  "stream:tasks:audio":       "Audio",
  "stream:tasks:stt":         "STT",
  "stream:tasks:nlp":         "NLP",
  "stream:tasks:llm":         "LLM",
  "stream:tasks:diagnostics": "Diag",
  "stream:tasks:aggregation": "Agg",
};

const COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"];

export function QueueDepthChart() {
  const { data, connected } = useDashboard();

  const chartData = data
    ? Object.entries(data.queues).map(([stream, count]) => ({
        name: STREAM_LABELS[stream] ?? stream.split(":").pop() ?? stream,
        count,
        stream,
      }))
    : [];

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-800">Queue Depths</h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="text-xs text-gray-500">{connected ? "Live" : "Reconnecting…"}</span>
        </div>
      </div>

      {data && (
        <div className="flex gap-4 mb-3 text-sm">
          <div className="bg-blue-50 rounded px-3 py-1">
            <span className="text-blue-600 font-semibold">{data.active_jobs}</span>
            <span className="text-blue-500 ml-1">running</span>
          </div>
          <div className="bg-gray-50 rounded px-3 py-1">
            <span className="text-gray-600 font-semibold">{data.pending_jobs}</span>
            <span className="text-gray-500 ml-1">pending</span>
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            formatter={(value: number) => [value, "Pending tasks"]}
            labelStyle={{ fontWeight: 600 }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
