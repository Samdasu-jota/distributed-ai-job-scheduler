"use client";

import { useState } from "react";
import { JobTable } from "@/components/JobTable";
import { WorkerStatusGrid } from "@/components/WorkerStatusGrid";
import { QueueDepthChart } from "@/components/QueueDepthChart";
import { ThroughputChart } from "@/components/ThroughputChart";
import { TaskDAGViewer } from "@/components/TaskDAGViewer";
import { JobSubmitForm } from "@/components/JobSubmitForm";

export default function DashboardPage() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-slate-900 text-white px-6 py-4 shadow">
        <div className="max-w-screen-xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              Distributed AI Job Scheduler
            </h1>
            <p className="text-slate-400 text-sm mt-0.5">
              English Tutoring Pipeline — Build Infrastructure Demo
            </p>
          </div>
          <div className="flex gap-4 text-xs text-slate-400">
            <span>Redis Streams</span>
            <span>·</span>
            <span>PostgreSQL</span>
            <span>·</span>
            <span>DAG Scheduling</span>
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-6 space-y-6">
        {/* Top row: Queue depths + Throughput */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <QueueDepthChart />
          <ThroughputChart />
        </div>

        {/* Worker status */}
        <WorkerStatusGrid />

        {/* Job submission */}
        <JobSubmitForm />

        {/* DAG viewer (shown when a job is selected) */}
        {selectedJobId && (
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-gray-700 font-medium">Task Graph</h2>
              <button
                onClick={() => setSelectedJobId(null)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                ✕ close
              </button>
            </div>
            <TaskDAGViewer jobId={selectedJobId} />
          </div>
        )}

        {/* Jobs table */}
        <JobTable onSelectJob={setSelectedJobId} />
      </main>
    </div>
  );
}
