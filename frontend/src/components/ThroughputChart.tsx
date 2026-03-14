"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DataPoint {
  minute: string;
  count: number;
}

export function ThroughputChart() {
  const [data, setData] = useState<DataPoint[]>([]);

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch(`${API_URL}/api/metrics/throughput`);
        const json = await res.json();
        const points = (json.jobs_per_minute ?? []).map((d: DataPoint) => ({
          ...d,
          minute: new Date(d.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        }));
        setData(points);
      } catch {
        // keep previous
      }
    };
    fetch_();
    const interval = setInterval(fetch_, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Job Throughput</h2>
      {data.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-gray-400 text-sm">
          No completed jobs in the last hour
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="minute" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip formatter={(v: number) => [v, "Jobs completed"]} />
            <Legend />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Jobs/min"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
