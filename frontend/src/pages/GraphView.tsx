import { useState, useEffect, useCallback, useMemo, useRef } from "react";
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

interface GraphNode {
  id: string;
  label: string;
  type: string;
  file?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

function getEndpointId(endpoint: unknown): string {
  if (typeof endpoint === "string") return endpoint;
  if (endpoint && typeof endpoint === "object" && "id" in endpoint) {
    return String((endpoint as { id: string }).id);
  }
  return String(endpoint ?? "");
}

export default function GraphView() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(new Set(NODE_TYPES));
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    api
      .getGraph()
      .then((graph) => {
        setData(graph);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const updateDimensions = () => {
      if (!containerRef.current) return;
      const { width, height } = containerRef.current.getBoundingClientRect();
      setDimensions({ width, height });
    };

    updateDimensions();

    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(containerRef.current);

    window.addEventListener("resize", updateDimensions);
    return () => {
      obs.disconnect();
      window.removeEventListener("resize", updateDimensions);
    };
  }, []);

  const nodes = useMemo(() => (data?.nodes ?? []) as GraphNode[], [data]);
  const edges = useMemo(() => (data?.edges ?? []) as any[], [data]);

  const nodeById = useMemo(() => {
    return new Map(nodes.map((node) => [node.id, node]));
  }, [nodes]);

  const filteredData = useMemo(() => {
    if (!data) return { nodes: [], links: [] as GraphEdge[] };

    const visibleNodeIds = new Set(
      nodes.filter((node) => visibleTypes.has(node.type)).map((node) => node.id),
    );

    return {
      nodes: nodes.filter((node) => visibleNodeIds.has(node.id)),
      links: edges
        .filter(
          (edge) =>
            visibleNodeIds.has(String(edge.source)) &&
            visibleNodeIds.has(String(edge.target)),
        )
        .map((edge) => ({
          source: String(edge.source),
          target: String(edge.target),
          relation: String(edge.type ?? edge.relation ?? "related"),
        })),
    };
  }, [data, nodes, edges, visibleTypes]);

  const fitGraph = useCallback((duration = 450, padding = 50) => {
    if (!graphRef.current) return;
    graphRef.current.zoomToFit(duration, padding);
  }, []);

  useEffect(() => {
    if (!graphRef.current || filteredData.nodes.length === 0) return;

    const timeout = window.setTimeout(() => fitGraph(450, 70), 120);
    return () => window.clearTimeout(timeout);
  }, [filteredData.nodes.length, filteredData.links.length, dimensions.width, dimensions.height, fitGraph]);

  const selectedNode = selected ? nodeById.get(selected) : undefined;

  const selectedNeighborhood = useMemo(() => {
    if (!selectedNode) {
      return {
        neighborIds: new Set<string>(),
        groupedByType: new Map<string, GraphNode[]>(),
      };
    }

    const neighborIds = new Set<string>();
    const groupedByType = new Map<string, GraphNode[]>();

    for (const edge of filteredData.links) {
      const source = getEndpointId(edge.source);
      const target = getEndpointId(edge.target);
      if (source !== selectedNode.id && target !== selectedNode.id) continue;

      const otherId = source === selectedNode.id ? target : source;
      const otherNode = nodeById.get(otherId);
      if (!otherNode) continue;

      neighborIds.add(otherId);
      if (!groupedByType.has(otherNode.type)) {
        groupedByType.set(otherNode.type, []);
      }
      groupedByType.get(otherNode.type)?.push(otherNode);
    }

    const dedupedGroupedByType = new Map<string, GraphNode[]>();
    for (const [type, list] of groupedByType) {
      const seen = new Set<string>();
      dedupedGroupedByType.set(
        type,
        list
          .filter((node) => {
            if (seen.has(node.id)) return false;
            seen.add(node.id);
            return true;
          })
          .sort((a, b) => a.label.localeCompare(b.label)),
      );
    }

    return { neighborIds, groupedByType: dedupedGroupedByType };
  }, [filteredData.links, nodeById, selectedNode]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of nodes) {
      counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
    }
    return counts;
  }, [nodes]);

  const toggleType = (t: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  };

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = 5;
      const isFocused = !selected || node.id === selected || selectedNeighborhood.neighborIds.has(node.id);

      ctx.globalAlpha = isFocused ? 1 : 0.16;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = NODE_COLORS[node.type] || "#94a3b8";
      ctx.fill();

      if (node.id === selected) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      const shouldRenderLabel = globalScale > 1.45 || node.id === selected;
      if (shouldRenderLabel) {
        const fontSize = 11 / globalScale;
        ctx.font = `${fontSize}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#334155";
        ctx.fillText(node.label || node.id, node.x, node.y + radius + 1.5);
      }

      ctx.globalAlpha = 1;
    },
    [selected, selectedNeighborhood.neighborIds],
  );

  const onEngineStop = useCallback(() => {
    fitGraph(260, 70);
  }, [fitGraph]);

  const showAllTypes = useCallback(() => {
    setVisibleTypes(new Set(NODE_TYPES));
  }, []);

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

  const graphWidth = dimensions.width > 0 ? dimensions.width : window.innerWidth;
  const graphHeight = dimensions.height > 0 ? dimensions.height : window.innerHeight;

  return (
    <div className="relative h-screen w-full overflow-hidden" ref={containerRef}>
      <div className="absolute top-4 left-4 z-20 rounded-xl border bg-card/95 px-3 py-2 shadow-sm backdrop-blur">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Filtres
        </div>
        <div className="flex max-w-[75vw] flex-wrap gap-2">
          {NODE_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => toggleType(t)}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                visibleTypes.has(t) ? "text-white" : "bg-muted text-muted-foreground"
              }`}
              style={visibleTypes.has(t) ? { backgroundColor: NODE_COLORS[t] } : {}}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: NODE_COLORS[t] }} />
              {t}
              <span className="opacity-80">{typeCounts.get(t) ?? 0}</span>
            </button>
          ))}
          <button
            onClick={showAllTypes}
            className="rounded border px-2.5 py-1 text-xs font-medium hover:bg-muted"
          >
            Tout afficher
          </button>
        </div>
      </div>

      {selectedNode && (
        <div className="absolute right-4 top-4 z-20 w-72 rounded-xl border bg-card/95 p-3 shadow-sm backdrop-blur">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{selectedNode.label}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: NODE_COLORS[selectedNode.type] || "#94a3b8" }}
                />
                <span className="capitalize">{selectedNode.type}</span>
              </div>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="rounded p-1 text-muted-foreground hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            Types connectes ({selectedNeighborhood.neighborIds.size})
          </div>
          <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-1">
            {NODE_TYPES.map((type) => {
              const nodesForType = selectedNeighborhood.groupedByType.get(type) ?? [];
              if (nodesForType.length === 0) return null;

              return (
                <div key={type}>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {type} ({nodesForType.length})
                  </div>
                  <ul className="space-y-0.5">
                    {nodesForType.map((node) => (
                      <li key={node.id} className="truncate text-xs text-foreground">
                        {node.label}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}

            {selectedNeighborhood.neighborIds.size === 0 && (
              <div className="text-xs text-muted-foreground">Aucun lien visible avec les filtres actuels.</div>
            )}
          </div>
        </div>
      )}

      <ForceGraph2D
        ref={graphRef}
        graphData={filteredData}
        width={graphWidth}
        height={graphHeight}
        nodeCanvasObject={nodeCanvasObject}
        onNodeClick={(node: any) => setSelected(node.id)}
        onBackgroundClick={() => setSelected(null)}
        enableNodeDrag={false}
        cooldownTicks={55}
        d3AlphaDecay={0.05}
        d3VelocityDecay={0.45}
        linkColor={(link: any) => {
          if (!selected) return "hsl(214, 20%, 82%)";
          const isNeighbor =
            String(link.source?.id ?? link.source) === selected ||
            String(link.target?.id ?? link.target) === selected;
          return isNeighbor ? "hsl(214, 70%, 45%)" : "hsl(214, 14%, 88%)";
        }}
        linkWidth={(link: any) => {
          if (!selected) return 0.9;
          const isNeighbor =
            String(link.source?.id ?? link.source) === selected ||
            String(link.target?.id ?? link.target) === selected;
          return isNeighbor ? 1.9 : 0.6;
        }}
        onEngineStop={onEngineStop}
      />
    </div>
  );
}
