import { useState, useEffect, useCallback, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Loader2, X } from "lucide-react";
import { api, type GraphData } from "@/lib/api";

const NODE_COLORS: Record<string, string> = {
  module: "#4981B9",
  class: "#899438",
  function: "#ED2C82",
  table: "#E09030",
  column: "#7B6CF6",
};

const NODE_TYPES = ["module", "class", "function", "table", "column"] as const;

export default function GraphView() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(new Set(NODE_TYPES));
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    api.getGraph()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const filteredData = data
    ? {
        nodes: data.nodes.filter((n) => visibleTypes.has(n.type)),
        links: data.edges
          .filter(
            (e) =>
              data.nodes.find((n) => n.id === String(e.source) && visibleTypes.has(n.type)) &&
              data.nodes.find((n) => n.id === String(e.target) && visibleTypes.has(n.type))
          )
          .map((e) => ({ source: String(e.source), target: String(e.target), relation: e.relation })),
      }
    : { nodes: [], links: [] };

  const selectedNode = data?.nodes.find((n) => n.id === selected);
  const neighbors = data
    ? data.edges
        .filter((e) => e.source === selected || e.target === selected)
        .map((e) => (e.source === selected ? e.target : e.source))
        .map((id) => data.nodes.find((n) => n.id === id)?.label || id)
    : [];

  const toggleType = (t: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  };

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.label || node.id;
      const fontSize = 12 / globalScale;
      const r = 6;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = NODE_COLORS[node.type] || "#999";
      ctx.fill();
      if (node.id === selected) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#333";
      ctx.fillText(label, node.x, node.y + r + 2);
    },
    [selected]
  );

  if (loading)
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );

  if (error)
    return (
      <div className="flex items-center justify-center h-screen text-accent text-sm">{error}</div>
    );

  if (!data || data.nodes.length === 0)
    return (
      <div className="flex items-center justify-center h-screen text-muted-foreground text-sm">
        No graph data available
      </div>
    );

  return (
    <div className="flex h-screen relative">
      {/* Filter bar */}
      <div className="absolute top-4 left-4 z-10 flex gap-2 bg-card/90 backdrop-blur rounded-lg px-3 py-2 border shadow-sm">
        {NODE_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => toggleType(t)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              visibleTypes.has(t)
                ? "text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
            style={visibleTypes.has(t) ? { backgroundColor: NODE_COLORS[t] } : {}}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: NODE_COLORS[t] }}
            />
            {t}
          </button>
        ))}
      </div>

      {/* Graph */}
      <div ref={containerRef} className="flex-1">
        <ForceGraph2D
          graphData={filteredData}
          width={dimensions.width - (selected ? 280 : 0)}
          height={dimensions.height}
          nodeCanvasObject={nodeCanvasObject}
          onNodeClick={(node: any) => setSelected(node.id)}
          onBackgroundClick={() => setSelected(null)}
          linkColor={() => "hsl(214, 20%, 85%)"}
          linkWidth={1}
          cooldownTicks={100}
        />
      </div>

      {/* Detail panel */}
      {selectedNode && (
        <div className="w-72 border-l bg-card p-5 overflow-y-auto">
          <div className="flex items-start justify-between mb-4">
            <h3 className="font-semibold text-sm">{selectedNode.label}</h3>
            <button onClick={() => setSelected(null)}>
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
          <div className="space-y-3">
            <div>
              <span className="text-xs text-muted-foreground">Type</span>
              <div className="flex items-center gap-2 mt-0.5">
                <span
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: NODE_COLORS[selectedNode.type] }}
                />
                <span className="text-sm capitalize">{selectedNode.type}</span>
              </div>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">
                Connected nodes ({neighbors.length})
              </span>
              <ul className="mt-1 space-y-0.5">
                {neighbors.map((n) => (
                  <li key={n} className="text-sm font-mono text-foreground">{n}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
