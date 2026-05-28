import { useEffect, useMemo, useRef, useState } from "react";
import { Send, RotateCcw, ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  api,
  type ChatDebugInfo,
  type ChatMessage,
  type ChatModelsResponse,
  type ChatResponse,
  type ChatSource,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const MODEL_STORAGE_KEY = "codenav.chat.model";

interface DisplayMessage extends ChatMessage {
  sources?: ChatSource[];
  debug?: ChatDebugInfo;
}

function formatDurationSeconds(durationMs?: number): string {
  if (typeof durationMs !== "number") {
    return "-";
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
}

function SourcesCollapsible({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Sources ({sources.length})
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 pl-4">
          {sources.map((source) => (
            <li key={source.chunk_id} className="font-mono text-xs text-muted-foreground">
              {source.source_file} [{source.chunk_type}] score={source.score}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DebugPanel({ debug }: { debug: ChatDebugInfo }) {
  const [open, setOpen] = useState(false);
  const retrieval = debug.retrieval_context ?? [];

  return (
    <div className="mt-2 rounded-md border border-border/70 bg-muted/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1">
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Details RAG
        </span>
        <span>
          {formatDurationSeconds(debug.duration_ms)} · tokens: {debug.tokens?.total ?? "-"}
        </span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-border/60 px-2 py-2 text-xs text-muted-foreground">
          {debug.vector_status === "unavailable" && (
            <div className="rounded border border-amber-300/60 bg-amber-100/40 px-2 py-1 text-[11px] text-amber-900">
              Base vectorielle indisponible: réponse en mode graphe uniquement.
            </div>
          )}

          <p>
            provider: <span className="font-mono">{debug.provider ?? "inconnu"}</span> | modèle: <span className="font-mono">{debug.model ?? "inconnu"}</span> | prompt tokens: {debug.tokens?.prompt ?? "-"} |
            completion tokens: {debug.tokens?.completion ?? "-"} | total tokens: {debug.tokens?.total ?? "-"}
          </p>

          {debug.vector_error && (
            <p className="font-mono text-[11px] text-muted-foreground/90">erreur_vectorielle: {debug.vector_error}</p>
          )}

          {retrieval.length > 0 && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Contexte injecté ({retrieval.length})</p>
              <ul className="space-y-1">
                {retrieval.map((context) => (
                  <li key={context.chunk_id} className="rounded border border-border/60 bg-background/40 p-2">
                    <p className="font-mono text-[11px]">
                      {context.source_file} [{context.chunk_type}] score={context.score}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-[11px] text-muted-foreground/90">
                      {context.content_excerpt}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {debug.graph_context && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Contexte graphe</p>
              <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded border border-border/60 bg-background/40 p-2 font-mono text-[11px]">
                {debug.graph_context}
              </pre>
            </div>
          )}

          {debug.prompt_preview && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Prompt enrichi (aperçu)</p>
              <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded border border-border/60 bg-background/40 p-2 font-mono text-[11px]">
                {debug.prompt_preview}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ModelSelector({
  models,
  loading,
  value,
  onChange,
}: {
  models: ChatModelsResponse | null;
  loading: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  const cloudModels = models?.models.filter((model) => model.deployment === "cloud") ?? [];
  const localModels = models?.models.filter((model) => model.deployment === "local") ?? [];

  if (loading) {
    return <Skeleton className="h-10 w-56 rounded-md" />;
  }

  if (!models || models.models.length === 0) {
    return <div className="text-xs text-muted-foreground">Aucun modèle disponible</div>;
  }

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-64">
        <SelectValue placeholder="Choisir un modèle" />
      </SelectTrigger>
      <SelectContent>
        {cloudModels.length > 0 && (
          <SelectGroup>
            <SelectLabel>☁️ Cloud</SelectLabel>
            {cloudModels.map((model) => (
              <SelectItem key={model.id} value={model.id}>
                {model.label}
              </SelectItem>
            ))}
          </SelectGroup>
        )}
        {localModels.length > 0 && cloudModels.length > 0 && <div className="my-1 h-px bg-muted" />}
        {localModels.length > 0 && (
          <SelectGroup>
            <SelectLabel>🖥 Local</SelectLabel>
            {localModels.map((model) => (
              <SelectItem key={model.id} value={model.id}>
                {model.label}
              </SelectItem>
            ))}
          </SelectGroup>
        )}
      </SelectContent>
    </Select>
  );
}

export default function ChatView() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ChatModelsResponse | null>(null);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const storedModel = localStorage.getItem(MODEL_STORAGE_KEY);

    const loadModels = async () => {
      try {
        const response = await api.getModels();
        setModels(response);

        const availableModelIds = new Set(response.models.map((model) => model.id));
        const nextModel = storedModel && availableModelIds.has(storedModel) ? storedModel : response.default_model;

        if (nextModel) {
          setSelectedModel(nextModel);
          localStorage.setItem(MODEL_STORAGE_KEY, nextModel);
        }
      } catch {
        if (storedModel) {
          setSelectedModel(storedModel);
        }
      } finally {
        setModelsLoading(false);
      }
    };

    void loadModels();
  }, []);

  const activeModelLabel = useMemo(() => {
    if (!selectedModel) {
      return "Modèle par défaut";
    }
    return models?.models.find((model) => model.id === selectedModel)?.label ?? selectedModel;
  }, [models, selectedModel]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) {
      return;
    }

    setInput("");
    setError(null);
    setLoading(true);

    const userMessage: DisplayMessage = { role: "user", content: text };
    const assistantPlaceholder: DisplayMessage = { role: "assistant", content: "" };
    setMessages((previous) => [...previous, userMessage, assistantPlaceholder]);

    let streamedAnswer = "";
    try {
      const response: ChatResponse = await api.chatStream(
        text,
        selectedModel || undefined,
        (delta) => {
          streamedAnswer += delta;
          setMessages((previous) => {
            const nextMessages = [...previous];
            const lastIndex = nextMessages.length - 1;
            const lastMessage = nextMessages[lastIndex];
            if (!lastMessage || lastMessage.role !== "assistant") {
              return nextMessages;
            }
            nextMessages[lastIndex] = {
              ...lastMessage,
              content: streamedAnswer,
            };
            return nextMessages;
          });
        },
      );

      setMessages((previous) => {
        const nextMessages = [...previous];
        const lastIndex = nextMessages.length - 1;
        nextMessages[lastIndex] = {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          debug: response.debug,
        };
        return nextMessages;
      });
    } catch (caughtError: any) {
      setMessages((previous) => previous.slice(0, -1));
      setError(caughtError.message || "Échec de la récupération de la réponse");
    } finally {
      setLoading(false);
    }
  };

  const reset = async () => {
    setMessages([]);
    setError(null);
    try {
      await api.resetChat();
    } catch {
      setError("Impossible de réinitialiser l'état du chat backend");
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <div className="flex items-center justify-between gap-4 border-b bg-card px-6 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <h2 className="text-lg font-semibold">Assistant</h2>
          <Badge variant="secondary" className="max-w-[280px] truncate">
            {modelsLoading ? "Chargement des modèles..." : activeModelLabel}
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <ModelSelector
            models={models}
            loading={modelsLoading}
            value={selectedModel}
            onChange={(nextModel) => {
              setSelectedModel(nextModel);
              localStorage.setItem(MODEL_STORAGE_KEY, nextModel);
            }}
          />
          <Button variant="ghost" size="sm" onClick={reset} className="text-muted-foreground">
            <RotateCcw className="mr-1 h-4 w-4" /> Reinitialiser
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
        {messages.length === 0 && !loading && (
          <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
            <MessageSquareIcon className="mb-3 h-12 w-12 opacity-30" />
            <p className="text-sm">Posez vos questions sur la codebase</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[75%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
              }`}
            >
              {message.role === "assistant" ? (
                <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:max-h-96 prose-pre:overflow-auto">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )}

              {message.role === "assistant" && message.debug?.vector_status === "unavailable" && (
                <p className="mt-2 inline-flex rounded-md border border-amber-300/70 bg-amber-100/50 px-2 py-0.5 text-[11px] text-amber-900">
                  Base vectorielle indisponible - mode graphe
                </p>
              )}

              {message.sources && message.sources.length > 0 && <SourcesCollapsible sources={message.sources} />}

              {message.role === "assistant" && message.debug && <DebugPanel debug={message.debug} />}
            </div>
          </div>
        ))}

        {error && <div className="rounded-md bg-accent/10 px-4 py-2 text-center text-sm text-accent">{error}</div>}

        <div ref={bottomRef} />
      </div>

      <div className="border-t bg-card px-6 py-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Posez une question sur la codebase..."
            className="flex-1 rounded-md border border-input bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !input.trim()} size="icon">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}

function MessageSquareIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
      />
    </svg>
  );
}
