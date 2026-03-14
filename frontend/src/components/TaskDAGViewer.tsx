"use client";

/**
 * TaskDAGViewer — renders the job's task dependency graph using ReactFlow.
 *
 * Nodes: pipeline stages, colored by status
 * Edges: dependency arrows (source → target = upstream → downstream)
 * Updates in real-time as tasks complete.
 */

import { useEffect, useState, useCallback } from "react";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DAGNode {
  id: string;
  stage_name: string;
  status: string;
  depends_on: string[];
  started_at: string | null;
  completed_at: string | null;
  worker_id: string | null;
  retry_count: number;
}

interface DAGEdge {
  source: string;
  target: string;
}

interface DAGData {
  job_id: string;
  nodes: DAGNode[];
  edges: DAGEdge[];
}

const STATUS_NODE_STYLES: Record<string, React.CSSProperties> = {
  PENDING:   { background: "#f3f4f6", border: "2px solid #d1d5db", color: "#374151" },
  ENQUEUED:  { background: "#dbeafe", border: "2px solid #3b82f6", color: "#1d4ed8" },
  RUNNING:   { background: "#fef9c3", border: "2px solid #eab308", color: "#854d0e" },
  COMPLETED: { background: "#dcfce7", border: "2px solid #22c55e", color: "#166534" },
  FAILED:    { background: "#fee2e2", border: "2px solid #ef4444", color: "#991b1b" },
  SKIPPED:   { background: "#f1f5f9", border: "2px solid #94a3b8", color: "#64748b" },
};

// Left-to-right layout positions for the 7 stages
const STAGE_POSITIONS: Record<string, { x: number; y: number }> = {
  audio_preprocessing:  { x: 0,   y: 200 },
  speech_to_text:       { x: 200, y: 200 },
  nlp_processing:       { x: 400, y: 100 },
  grammar_correction:   { x: 400, y: 300 },
  natural_phrasing:     { x: 600, y: 300 },
  diagnostics:          { x: 800, y: 200 },
  aggregation:          { x: 1000, y: 200 },
};

const STAGE_LABELS: Record<string, string> = {
  audio_preprocessing: "Audio\nPreprocessing",
  speech_to_text:      "Speech-to-Text",
  nlp_processing:      "NLP\nProcessing",
  grammar_correction:  "Grammar\nCorrection",
  natural_phrasing:    "Natural\nPhrasing",
  diagnostics:         "Diagnostics\n(fan-in)",
  aggregation:         "Aggregation",
};

function dagToFlow(dag: DAGData): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = dag.nodes.map((n) => ({
    id: n.id,
    position: STAGE_POSITIONS[n.stage_name] ?? { x: 0, y: 0 },
    data: {
      label: (
        <div className="text-center px-1">
          <div className="font-semibold text-xs leading-tight whitespace-pre-line">
            {STAGE_LABELS[n.stage_name] ?? n.stage_name}
          </div>
          <div className="text-xs mt-0.5 opacity-80">{n.status}</div>
          {n.retry_count > 0 && (
            <div className="text-xs text-orange-600">retry {n.retry_count}</div>
          )}
        </div>
      ),
    },
    style: {
      ...(STATUS_NODE_STYLES[n.status] ?? STATUS_NODE_STYLES["PENDING"]),
      borderRadius: "8px",
      padding: "8px 12px",
      fontSize: "12px",
      minWidth: "110px",
      minHeight: "60px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    },
  }));

  const edges: Edge[] = dag.edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "#6b7280", strokeWidth: 2 },
    markerEnd: { type: "arrowclosed" } as any,
  }));

  return { nodes, edges };
}

export function TaskDAGViewer({ jobId }: { jobId: string }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  const fetchDAG = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/dag`);
      if (!res.ok) return;
      const dag: DAGData = await res.json();
      const { nodes: n, edges: e } = dagToFlow(dag);
      setNodes(n);
      setEdges(e);
    } catch {
      // keep previous
    } finally {
      setLoading(false);
    }
  }, [jobId, setNodes, setEdges]);

  useEffect(() => {
    fetchDAG();
    const interval = setInterval(fetchDAG, 2000);
    return () => clearInterval(interval);
  }, [fetchDAG]);

  if (loading) {
    return <div className="h-96 flex items-center justify-center text-gray-400">Loading DAG…</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold text-gray-800">Task Dependency Graph</h2>
        <p className="text-xs text-gray-500 mt-0.5">Job: {jobId.slice(0, 8)}…</p>
      </div>
      <div style={{ height: 420 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Background color="#f0f0f0" />
          <Controls showInteractive={false} />
          <MiniMap nodeColor={(n) => {
            const style = STATUS_NODE_STYLES[
              (n.style as Record<string, string>)?.["background"] ?? "PENDING"
            ];
            return (style?.background as string) ?? "#ccc";
          }} />
        </ReactFlow>
      </div>

      {/* Status legend */}
      <div className="px-4 pb-3 flex flex-wrap gap-2">
        {Object.entries(STATUS_NODE_STYLES).map(([status, style]) => (
          <span
            key={status}
            className="text-xs px-2 py-0.5 rounded border font-medium"
            style={{ background: style.background as string, borderColor: style.border?.split(" ").pop(), color: style.color as string }}
          >
            {status}
          </span>
        ))}
      </div>
    </div>
  );
}
