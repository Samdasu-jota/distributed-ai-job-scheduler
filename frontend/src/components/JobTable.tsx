"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Job {
  job_id: string;
  status: string;
  submitted_at: string;
  completed_at: string | null;
  user_id: string | null;
  priority: number;
  tasks: { status: string }[];
}

const STATUS_COLORS: Record<string, string> = {
  PENDING:   "bg-gray-200 text-gray-700",
  RUNNING:   "bg-yellow-200 text-yellow-800",
  COMPLETED: "bg-green-200 text-green-800",
  FAILED:    "bg-red-200 text-red-800",
  CANCELLED: "bg-slate-200 text-slate-700",
};

export function JobTable({ onSelectJob }: { onSelectJob: (id: string) => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_URL}/api/jobs?limit=30`);
      const data = await res.json();
      setJobs(data.jobs ?? []);
    } catch {
      // keep previous data
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const calcDuration = (job: Job) => {
    if (!job.completed_at) return "—";
    const start = new Date(job.submitted_at).getTime();
    const end = new Date(job.completed_at).getTime();
    return `${((end - start) / 1000).toFixed(1)}s`;
  };

  const taskProgress = (job: Job) => {
    const completed = job.tasks.filter(t => t.status === "COMPLETED").length;
    return `${completed}/${job.tasks.length}`;
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Jobs</h2>
        <span className="text-sm text-gray-500">{jobs.length} total</span>
      </div>
      {loading ? (
        <div className="p-8 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Job ID</th>
                <th className="text-left p-3 font-medium text-gray-600">Status</th>
                <th className="text-left p-3 font-medium text-gray-600">Priority</th>
                <th className="text-left p-3 font-medium text-gray-600">Tasks</th>
                <th className="text-left p-3 font-medium text-gray-600">Duration</th>
                <th className="text-left p-3 font-medium text-gray-600">User</th>
                <th className="text-left p-3 font-medium text-gray-600"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((job) => (
                <tr key={job.job_id} className="hover:bg-gray-50">
                  <td className="p-3 font-mono text-xs text-gray-600">
                    {job.job_id.slice(0, 8)}…
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[job.status] ?? "bg-gray-100"}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="p-3 text-gray-600">{job.priority}</td>
                  <td className="p-3 text-gray-600">{taskProgress(job)}</td>
                  <td className="p-3 text-gray-600 font-mono text-xs">{calcDuration(job)}</td>
                  <td className="p-3 text-gray-500 text-xs">{job.user_id ?? "—"}</td>
                  <td className="p-3">
                    <button
                      onClick={() => onSelectJob(job.job_id)}
                      className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                    >
                      View DAG →
                    </button>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-gray-400">
                    No jobs yet. Submit one via POST /api/jobs
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
