import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import dagre from "dagre";
import ForceGraph2D from "react-force-graph-2d";
import { Loader2, X } from "lucide-react";
import { api, type GraphData } from "@/lib/api";

const TYPE_COLORS: Record<string, string> = {
  module: "#4981B9",
  class: "#899438",
  function: "#ED2C82",
  table: "#E09030",
  column: "#7B6CF6",
};

const SCRIPT_TYPES = new Set(["module", "class", "function"]);

const LAYOUT_OPTIONS = [
  { id: "free", label: "Libre" },
  { id: "lr", label: "Gauche a droite" },
  { id: "bt", label: "Bas en haut" },
] as const;

const NODE_TYPES = ["module", "class", "function", "table"] as const;
type LayoutMode = (typeof LAYOUT_OPTIONS)[number]["id"];

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

interface RenderNode extends GraphNode {
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

function getEndpointId(endpoint: unknown): string {
  if (typeof endpoint === "string") return endpoint;
  if (endpoint && typeof endpoint === "object" && "id" in endpoint) {
    return String((endpoint as { id: string }).id);
  }
  return String(endpoint ?? "");
}

function isDependencyRelation(relation: string): boolean {
  return relation === "depends_on" || relation === "reads_table" || relation === "writes_table";
}

function getNodeBox(node: GraphNode): { width: number; height: number } {
  if (node.type === "table") return { width: 26, height: 16 };
  if (SCRIPT_TYPES.has(node.type)) return { width: 20, height: 20 };
  return { width: 12, height: 12 };
}

export default function GraphView() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("free");
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

  const graphNodes = useMemo(() => nodes.filter((node) => node.type !== "column"), [nodes]);

  const nodeById = useMemo(() => {
    return new Map(graphNodes.map((node) => [node.id, node]));
  }, [graphNodes]);

  const autocompleteNodes = useMemo(() => {
    return [...graphNodes].sort((a, b) => a.label.localeCompare(b.label));
  }, [graphNodes]);

  const filteredData = useMemo(() => {
    if (!data) return { nodes: [], links: [] as GraphEdge[] };

    const visibleNodeIds = new Set(
      graphNodes.filter((node) => visibleTypes.has(node.type)).map((node) => node.id),
    );

    return {
      nodes: graphNodes.filter((node) => visibleNodeIds.has(node.id)),
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
  }, [data, graphNodes, edges, visibleTypes]);

  const graphData = useMemo(() => {
    const baseNodes: RenderNode[] = filteredData.nodes.map((node) => ({ ...node }));
    const links: GraphEdge[] = filteredData.links.map((edge) => ({ ...edge }));

    if (layoutMode === "free") {
      return {
        nodes: baseNodes.map((node) => ({ ...node, fx: undefined, fy: undefined })),
        links,
      };
    }

    const dag = new dagre.graphlib.Graph();
    dag.setGraph({
      rankdir: layoutMode === "lr" ? "LR" : "BT",
      nodesep: 22,
      ranksep: 62,
      marginx: 20,
      marginy: 20,
    });
    dag.setDefaultEdgeLabel(() => ({}));

    for (const node of baseNodes) {
      const { width, height } = getNodeBox(node);
      dag.setNode(node.id, { width, height });
    }

    const layoutLinks = links.filter((edge) => isDependencyRelation(edge.relation));
    const edgesToUse = layoutLinks.length > 0 ? layoutLinks : links;
    for (const edge of edgesToUse) {
      dag.setEdge(edge.source, edge.target);
    }

    dagre.layout(dag);

    return {
      nodes: baseNodes.map((node) => {
        const coords = dag.node(node.id) as { x: number; y: number } | undefined;
        if (!coords) return { ...node, fx: undefined, fy: undefined };
        return {
          ...node,
          x: coords.x,
          y: coords.y,
          fx: layoutMode === "lr" ? coords.x : undefined,
          fy: layoutMode === "bt" ? coords.y : undefined,
        };
      }),
      links,
    };
  }, [filteredData.links, filteredData.nodes, layoutMode]);

  const fitGraph = useCallback((duration = 450, padding = 50) => {
    if (!graphRef.current) return;
    graphRef.current.zoomToFit(duration, padding);
  }, []);

  useEffect(() => {
    if (!graphRef.current || graphData.nodes.length === 0) return;

    const timeout = window.setTimeout(() => fitGraph(450, 70), 120);
    return () => window.clearTimeout(timeout);
  }, [graphData.nodes.length, graphData.links.length, dimensions.width, dimensions.height, layoutMode, fitGraph]);

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

    for (const edge of graphData.links) {
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
  }, [graphData.links, nodeById, selectedNode]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of graphNodes) {
      counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
    }
    return counts;
  }, [graphNodes]);

  const toggleType = (t: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  };

  const focusNode = useCallback((nodeId: string) => {
    const targetNode = nodeById.get(nodeId);
    if (!targetNode) return;

    setVisibleTypes((prev) => {
      const next = new Set(prev);
      next.add(targetNode.type);
      return next;
    });
    setSelected(nodeId);

    window.setTimeout(() => {
      if (!graphRef.current) return;
      const liveNodes = (graphRef.current.graphData()?.nodes ?? []) as Array<{
        id: string;
        x?: number;
        y?: number;
      }>;
      const liveNode = liveNodes.find((n) => n.id === nodeId);
      if (!liveNode || typeof liveNode.x !== "number" || typeof liveNode.y !== "number") return;

      graphRef.current.centerAt(liveNode.x, liveNode.y, 550);
      graphRef.current.zoom(2.6, 550);
    }, 140);
  }, [nodeById]);

  const trySelectBySearch = useCallback(
    (raw: string) => {
      const query = raw.trim().toLowerCase();
      if (!query) return;

      const exact = autocompleteNodes.find((node) => node.label.toLowerCase() === query);
      if (!exact) return;

      focusNode(exact.id);
    },
    [autocompleteNodes, focusNode],
  );

  const nodeCanvasObject = useCallback(
    (node: RenderNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = 5;
      const isFocused = !selected || node.id === selected || selectedNeighborhood.neighborIds.has(node.id);

      ctx.globalAlpha = isFocused ? 1 : 0.16;
      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
      ctx.fillStyle = TYPE_COLORS[node.type] || "#94a3b8";
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
        ctx.fillText(node.label || node.id, node.x ?? 0, (node.y ?? 0) + radius + 1.5);
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
        Aucune donnee de graphe disponible
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
        <div className="mb-3 flex flex-wrap gap-2">
          {LAYOUT_OPTIONS.map((mode) => (
            <button
              key={mode.id}
              onClick={() => setLayoutMode(mode.id)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                layoutMode === mode.id
                  ? "bg-foreground text-background"
                  : "border text-muted-foreground hover:bg-muted"
              }`}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <div className="mb-3">
          <input
            list="graph-node-autocomplete"
            value={searchTerm}
            onChange={(e) => {
              const value = e.target.value;
              setSearchTerm(value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                trySelectBySearch(searchTerm);
              }
            }}
            onBlur={() => trySelectBySearch(searchTerm)}
            placeholder="Rechercher un noeud..."
            className="w-full rounded border bg-background px-2.5 py-1.5 text-xs outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2"
          />
          <datalist id="graph-node-autocomplete">
            {autocompleteNodes.map((node) => (
              <option key={node.id} value={node.label} />
            ))}
          </datalist>
        </div>
        <div className="flex max-w-[75vw] flex-wrap gap-2">
          {NODE_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => toggleType(t)}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                visibleTypes.has(t) ? "text-white" : "bg-muted text-muted-foreground"
              }`}
              style={visibleTypes.has(t) ? { backgroundColor: TYPE_COLORS[t] } : {}}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: TYPE_COLORS[t] }} />
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
                  style={{ backgroundColor: TYPE_COLORS[selectedNode.type] || "#94a3b8" }}
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
        graphData={graphData}
        width={graphWidth}
        height={graphHeight}
        nodeCanvasObject={nodeCanvasObject}
        onNodeClick={(node: any) => {
          setSelected(node.id);
          const clickedNode = nodeById.get(String(node.id));
          if (clickedNode) setSearchTerm(clickedNode.label);
        }}
        onBackgroundClick={() => {
          setSelected(null);
          setSearchTerm("");
        }}
        enableNodeDrag={true}
        cooldownTicks={layoutMode === "free" ? 55 : 80}
        d3AlphaDecay={layoutMode === "free" ? 0.05 : 0.08}
        d3VelocityDecay={layoutMode === "free" ? 0.45 : 0.3}
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
        linkDirectionalArrowLength={(link: any) =>
          isDependencyRelation(String(link.relation ?? link.type ?? "")) ? 3.8 : 0
        }
        linkDirectionalArrowRelPos={1}
        onEngineStop={onEngineStop}
      />
    </div>
  );
}
