import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Play, RefreshCw, Database, ExternalLink, RotateCcw } from "lucide-react";
import { api, type PipelineRunRequest, type PipelineStatus, type QdrantInfo } from "@/lib/api";
import { Button } from "@/components/ui/button";

const defaultForm: PipelineRunRequest = {
  repo: "",
  output_docs: "data/output/docs",
  output_graph: "data/output/graph",
  recreate: false,
  dialect: "mysql",
  dry_run: false,
};

export default function PipelineView() {
  const [form, setForm] = useState<PipelineRunRequest>(defaultForm);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [qdrant, setQdrant] = useState<QdrantInfo | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [refreshingQdrant, setRefreshingQdrant] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const next = await api.getPipelineStatus();
      setStatus(next);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Impossible de recuperer le statut pipeline");
    } finally {
      setLoadingStatus(false);
    }
  };

  const fetchQdrant = async () => {
    setRefreshingQdrant(true);
    try {
      const info = await api.getQdrantInfo();
      setQdrant(info);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Impossible de verifier Qdrant");
    } finally {
      setRefreshingQdrant(false);
    }
  };

  useEffect(() => {
    void fetchStatus();
    void fetchQdrant();
  }, []);

  useEffect(() => {
    const running = status?.status === "running" || status?.status === "queued";
    const interval = window.setInterval(() => {
      void fetchStatus();
    }, running ? 1500 : 5000);
    return () => window.clearInterval(interval);
  }, [status?.status]);

  const runPipeline = async () => {
    if (!form.repo.trim()) {
      setError("Le champ repo est requis.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.startPipeline(form);
      await fetchStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Echec du lancement pipeline");
    } finally {
      setSubmitting(false);
    }
  };

  const resetStatus = async () => {
    try {
      const next = await api.resetPipelineStatus();
      setStatus(next);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Impossible de reinitialiser le statut");
    }
  };

  const openQdrant = async () => {
    try {
      const url = qdrant?.url ?? (await api.openQdrant()).url;
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Impossible d'ouvrir Qdrant");
    }
  };

  const isRunning = status?.status === "running" || status?.status === "queued";

  const recentEvents = useMemo(() => {
    const events = status?.events ?? [];
    return [...events].reverse();
  }, [status?.events]);

  const clampedProgress = Math.max(0, Math.min(100, status?.progress ?? 0));

  return (
    <div className="h-screen overflow-y-auto px-6 py-6 bg-background">
      <div className="max-w-6xl mx-auto space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Pipeline d'indexation</h2>
            <p className="text-sm text-muted-foreground">
              Lance le meme workflow que le CLI: parsing, embeddings, docs, graph, diagrammes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => void fetchStatus()}>
              <RefreshCw className="w-4 h-4 mr-1" /> Rafraichir
            </Button>
            <Button variant="outline" onClick={resetStatus} disabled={isRunning}>
              <RotateCcw className="w-4 h-4 mr-1" /> Reset statut
            </Button>
          </div>
        </div>

        <section className="rounded-lg border bg-card p-4 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Arguments</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm">Repository path ou URL Git</span>
              <input
                value={form.repo}
                onChange={(e) => setForm((prev) => ({ ...prev, repo: e.target.value }))}
                placeholder="data/input/sample_repo"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm">Output docs</span>
              <input
                value={form.output_docs}
                onChange={(e) => setForm((prev) => ({ ...prev, output_docs: e.target.value }))}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm">Output graph</span>
              <input
                value={form.output_graph}
                onChange={(e) => setForm((prev) => ({ ...prev, output_graph: e.target.value }))}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm">SQL dialect</span>
              <input
                value={form.dialect}
                onChange={(e) => setForm((prev) => ({ ...prev, dialect: e.target.value }))}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>

            <div className="flex flex-wrap gap-5 items-center pt-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.recreate}
                  onChange={(e) => setForm((prev) => ({ ...prev, recreate: e.target.checked }))}
                />
                Recreate collection
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.dry_run}
                  onChange={(e) => setForm((prev) => ({ ...prev, dry_run: e.target.checked }))}
                />
                Dry-run index (sans embeddings)
              </label>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={runPipeline} disabled={submitting || isRunning}>
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" /> Lancement...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-1" /> Lancer le pipeline
                </>
              )}
            </Button>
          </div>
        </section>

        <section className="rounded-lg border bg-card p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Qdrant</h3>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void fetchQdrant()} disabled={refreshingQdrant}>
                <Database className="w-4 h-4 mr-1" /> Verifier
              </Button>
              <Button variant="outline" onClick={openQdrant}>
                <ExternalLink className="w-4 h-4 mr-1" /> Ouvrir dashboard
              </Button>
            </div>
          </div>

          {qdrant ? (
            <div className="text-sm space-y-1">
              <p>
                Etat: <strong>{qdrant.reachable ? "connecte" : "indisponible"}</strong> ({qdrant.host}:{qdrant.port})
              </p>
              <p>Collection active: {qdrant.active_collection}</p>
              <p>
                Collections: {qdrant.collections.length > 0 ? qdrant.collections.join(", ") : "aucune"}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Chargement des infos Qdrant...</p>
          )}
        </section>

        <section className="rounded-lg border bg-card p-4 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Progression</h3>

          {loadingStatus ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" /> Chargement du statut...
            </div>
          ) : status ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <p>
                  Statut: <strong>{status.status}</strong>
                </p>
                <p>
                  Stage: <strong>{status.current_stage}</strong>
                </p>
                <p>Fichiers detectes: {status.stats.files}</p>
                <p>Fichiers parses: {status.stats.parsed_files}</p>
                <p>Chunks: {status.stats.chunks}</p>
                <p>Embeddings: {status.stats.embeddings}</p>
              </div>

              <div className="space-y-1">
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full w-full origin-left transition-transform"
                    style={{
                      transform: `scaleX(${clampedProgress / 100})`,
                      backgroundImage:
                        "linear-gradient(90deg, #0057B8 0%, #EA4C89 52%, #22A55D 100%)",
                    }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{status.progress.toFixed(1)}%</p>
              </div>

              {status.error && <p className="text-sm text-accent">{status.error}</p>}

              {status.status === "succeeded" && (
                <div className="rounded-md border bg-muted/30 p-3 text-sm space-y-2">
                  <p>Pipeline termine. Vous pouvez maintenant utiliser les vues ci-dessous:</p>
                  <div className="flex flex-wrap gap-2">
                    <Link to="/">
                      <Button size="sm">Chat</Button>
                    </Link>
                    <Link to="/docs">
                      <Button size="sm" variant="outline">Documentation</Button>
                    </Link>
                    <Link to="/graph">
                      <Button size="sm" variant="outline">Knowledge Graph</Button>
                    </Link>
                    <Link to="/diagrams">
                      <Button size="sm" variant="outline">Diagrammes</Button>
                    </Link>
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Aucune execution pipeline pour le moment.</p>
          )}
        </section>

        <section className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">Journal detaille</h3>
          {recentEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun evenement pour le moment.</p>
          ) : (
            <div className="max-h-[380px] overflow-y-auto border rounded-md">
              <ul className="divide-y text-sm">
                {recentEvents.map((event, index) => (
                  <li key={`${event.timestamp}-${index}`} className="px-3 py-2">
                    <p className="font-medium">[{event.stage}] {event.message}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(event.timestamp).toLocaleString()} - {event.progress.toFixed(1)}%
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {error && (
          <div className="rounded-md border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-accent">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
