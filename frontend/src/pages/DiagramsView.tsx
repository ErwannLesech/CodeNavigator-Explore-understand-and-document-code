import { useEffect, useMemo, useRef, useState } from "react";
import mermaid from "mermaid";
import { FileCode2, Loader2, Search } from "lucide-react";
import { api, type DiagramItem } from "@/lib/api";

let mermaidInitialized = false;

function ensureMermaidInitialized(): void {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "default",
  });
  mermaidInitialized = true;
}

export default function DiagramsView() {
  const [diagrams, setDiagrams] = useState<DiagramItem[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [diagramCode, setDiagramCode] = useState("");
  const [search, setSearch] = useState("");
  const [listLoading, setListLoading] = useState(true);
  const [diagramLoading, setDiagramLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [baseSize, setBaseSize] = useState({ width: 0, height: 0 });
  const dragAnchorRef = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  const clampZoom = (value: number) => Math.min(4, Math.max(0.2, value));

  useEffect(() => {
    ensureMermaidInitialized();

    api
      .getDiagrams()
      .then((response) => {
        setDiagrams(response.diagrams ?? []);
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Failed to load diagrams";
        setListError(message);
      })
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedName) {
      setDiagramCode("");
      setRenderError(null);
      return;
    }

    setDiagramLoading(true);
    setRenderError(null);

    api
      .getDiagram(selectedName)
      .then((response) => {
        setDiagramCode(response.content);
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Failed to load diagram";
        setRenderError(message);
        setDiagramCode("");
      })
      .finally(() => setDiagramLoading(false));
  }, [selectedName]);

  useEffect(() => {
    setZoom(1);
    setBaseSize({ width: 0, height: 0 });
    setDragging(false);
    dragAnchorRef.current = null;
  }, [selectedName]);

  useEffect(() => {
    if (!previewRef.current) return;

    const host = previewRef.current;
    if (!diagramCode.trim()) {
      host.innerHTML = "";
      return;
    }

    const render = async () => {
      try {
        const renderId = `mermaid-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
        const { svg } = await mermaid.render(renderId, diagramCode);
        host.innerHTML = svg;

        const svgElement = host.querySelector("svg");
        if (svgElement) {
          const viewBox = svgElement.getAttribute("viewBox")?.split(/\s+/).map(Number);
          const parsedWidth = Number(svgElement.getAttribute("width")?.replace("px", ""));
          const parsedHeight = Number(svgElement.getAttribute("height")?.replace("px", ""));
          const naturalWidth =
            viewBox && viewBox.length === 4 && Number.isFinite(viewBox[2]) ? viewBox[2] : parsedWidth;
          const naturalHeight =
            viewBox && viewBox.length === 4 && Number.isFinite(viewBox[3]) ? viewBox[3] : parsedHeight;

          if (Number.isFinite(naturalWidth) && Number.isFinite(naturalHeight)) {
            setBaseSize({ width: naturalWidth, height: naturalHeight });
          }

          svgElement.style.display = "block";
          svgElement.style.maxWidth = "none";
          svgElement.style.width = "max-content";
          svgElement.style.height = "max-content";
          svgElement.style.textRendering = "geometricPrecision";
          svgElement.style.shapeRendering = "geometricPrecision";
          svgElement.style.pointerEvents = "none";
        }

        setRenderError(null);
      } catch (error: unknown) {
        host.innerHTML = "";
        const message = error instanceof Error ? error.message : "Invalid Mermaid diagram";
        setRenderError(`Rendering error: ${message}`);
      }
    };

    void render();
  }, [diagramCode]);

  useEffect(() => {
    if (!previewRef.current || baseSize.width <= 0 || baseSize.height <= 0) return;
    const svgElement = previewRef.current.querySelector("svg");
    if (!svgElement) return;
    svgElement.style.width = `${baseSize.width * zoom}px`;
    svgElement.style.height = `${baseSize.height * zoom}px`;
  }, [zoom, baseSize.width, baseSize.height]);

  const filteredDiagrams = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return diagrams;
    return diagrams.filter((diagram) => diagram.name.toLowerCase().includes(query));
  }, [diagrams, search]);

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const viewport = viewportRef.current;
    if (!viewport) return;

    const rect = viewport.getBoundingClientRect();
    const localX = event.clientX - rect.left;
    const localY = event.clientY - rect.top;
    const worldX = (viewport.scrollLeft + localX) / zoom;
    const worldY = (viewport.scrollTop + localY) / zoom;

    const nextZoom = clampZoom(zoom * (event.deltaY < 0 ? 1.12 : 0.89));
    setZoom(nextZoom);

    requestAnimationFrame(() => {
      viewport.scrollLeft = worldX * nextZoom - localX;
      viewport.scrollTop = worldY * nextZoom - localY;
    });
  };

  const onMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const viewport = viewportRef.current;
    if (!viewport) return;

    setDragging(true);
    dragAnchorRef.current = {
      x: event.clientX,
      y: event.clientY,
      left: viewport.scrollLeft,
      top: viewport.scrollTop,
    };
  };

  const onMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!dragging || !dragAnchorRef.current) return;
    const viewport = viewportRef.current;
    if (!viewport) return;

    const dx = event.clientX - dragAnchorRef.current.x;
    const dy = event.clientY - dragAnchorRef.current.y;
    viewport.scrollLeft = dragAnchorRef.current.left - dx;
    viewport.scrollTop = dragAnchorRef.current.top - dy;
  };

  const endDrag = () => {
    setDragging(false);
    dragAnchorRef.current = null;
  };

  const resetView = () => {
    setZoom(1);
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  };

  return (
    <div className="flex h-screen">
      <aside className="w-80 flex-shrink-0 border-r bg-card overflow-y-auto">
        <div className="px-4 py-3 border-b space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Diagrammes Mermaid
          </h2>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search diagrams..."
              className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        {listLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : listError ? (
          <p className="text-sm text-accent px-4 py-3">{listError}</p>
        ) : filteredDiagrams.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 py-3">Aucun diagramme trouve.</p>
        ) : (
          <ul className="py-1">
            {filteredDiagrams.map((diagram) => (
              <li key={diagram.name}>
                <button
                  onClick={() => setSelectedName(diagram.name)}
                  className={`w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    selectedName === diagram.name
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-foreground hover:bg-muted"
                  }`}
                >
                  <FileCode2 className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">{diagram.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <main className="flex-1 overflow-hidden bg-background p-6">
        {!selectedName ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Selectionne un diagramme Mermaid dans la liste.
          </div>
        ) : diagramLoading ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : renderError ? (
          <div className="space-y-3">
            <p className="text-sm text-accent">{renderError}</p>
            {diagramCode && (
              <pre className="max-h-[70vh] overflow-auto rounded-md border bg-card p-3 text-xs">
                {diagramCode}
              </pre>
            )}
          </div>
        ) : (
          <div className="h-full min-h-0 rounded-lg border bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Molette: zoom | Clic gauche + glisser: deplacement
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setZoom((current) => clampZoom(current * 0.9))}
                  className="rounded border px-2 py-1 text-xs font-medium hover:bg-muted"
                >
                  -
                </button>
                <span className="w-14 text-center text-xs text-muted-foreground">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoom((current) => clampZoom(current * 1.1))}
                  className="rounded border px-2 py-1 text-xs font-medium hover:bg-muted"
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={resetView}
                  className="rounded border px-2 py-1 text-xs font-medium hover:bg-muted"
                >
                  Reset
                </button>
              </div>
            </div>

            <div
              ref={viewportRef}
              onWheel={onWheel}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={endDrag}
              onMouseLeave={endDrag}
              className={`h-[calc(100%-2.25rem)] overflow-auto rounded border bg-slate-50 ${
                dragging ? "cursor-grabbing" : "cursor-grab"
              }`}
            >
              <div
                style={{
                  padding: "24px",
                  width: baseSize.width > 0 ? `${baseSize.width * zoom + 48}px` : "max-content",
                  height: baseSize.height > 0 ? `${baseSize.height * zoom + 48}px` : "max-content",
                }}
              >
                <div ref={previewRef} className="select-none" />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
