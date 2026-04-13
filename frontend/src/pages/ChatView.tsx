import { useState, useRef, useEffect } from "react";
import { Send, RotateCcw, ChevronDown, ChevronRight } from "lucide-react";
import {
  api,
  type ChatMessage,
  type ChatResponse,
  type ChatSource,
  type ChatDebugInfo,
} from "@/lib/api";
import { Button } from "@/components/ui/button";

interface DisplayMessage extends ChatMessage {
  sources?: ChatSource[];
  debug?: ChatDebugInfo;
}

function SourcesCollapsible({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Sources ({sources.length})
      </button>
      {open && (
        <ul className="mt-1 pl-4 space-y-0.5">
          {sources.map((s) => (
            <li key={s.chunk_id} className="text-xs font-mono text-muted-foreground">
              {s.source_file} [{s.chunk_type}] score={s.score}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-primary animate-bounce"
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
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
          Debug RAG
        </span>
        <span>
          {debug.duration_ms ? `${debug.duration_ms} ms` : "-"} · tokens: {debug.tokens?.total ?? "-"}
        </span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-border/60 px-2 py-2 text-xs text-muted-foreground">
          {debug.vector_status === "unavailable" && (
            <div className="rounded border border-amber-300/60 bg-amber-100/40 px-2 py-1 text-[11px] text-amber-900">
              Base vectorielle indisponible: reponse en mode graphe uniquement.
            </div>
          )}

          <p>
            model: <span className="font-mono">{debug.model ?? "unknown"}</span> | prompt: {debug.tokens?.prompt ?? "-"} |
            completion: {debug.tokens?.completion ?? "-"} | total: {debug.tokens?.total ?? "-"}
          </p>

          {debug.vector_error && (
            <p className="font-mono text-[11px] text-muted-foreground/90">vector_error: {debug.vector_error}</p>
          )}

          {retrieval.length > 0 && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Contexte injecte ({retrieval.length})</p>
              <ul className="space-y-1">
                {retrieval.map((ctx) => (
                  <li key={ctx.chunk_id} className="rounded border border-border/60 bg-background/40 p-2">
                    <p className="font-mono text-[11px]">
                      {ctx.source_file} [{ctx.chunk_type}] score={ctx.score}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-[11px] text-muted-foreground/90">
                      {ctx.content_excerpt}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {debug.graph_context && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Contexte graphe</p>
              <pre className="max-h-44 overflow-auto rounded border border-border/60 bg-background/40 p-2 font-mono text-[11px] whitespace-pre-wrap">
                {debug.graph_context}
              </pre>
            </div>
          )}

          {debug.prompt_preview && (
            <div className="space-y-1">
              <p className="font-semibold text-foreground/80">Prompt enrichi (apercu)</p>
              <pre className="max-h-44 overflow-auto rounded border border-border/60 bg-background/40 p-2 font-mono text-[11px] whitespace-pre-wrap">
                {debug.prompt_preview}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatView() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);

    const userMsg: DisplayMessage = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);

    setLoading(true);
    try {
      const res: ChatResponse = await api.chat(text);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          debug: res.debug,
        },
      ]);
    } catch (e: any) {
      setError(e.message || "Failed to get response");
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
      setError("Failed to reset backend chat state");
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b bg-card">
        <h2 className="text-lg font-semibold">Chat</h2>
        <Button variant="ghost" size="sm" onClick={reset} className="text-muted-foreground">
          <RotateCcw className="w-4 h-4 mr-1" /> Reset
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <MessageSquareIcon className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">Ask anything about the codebase</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === "assistant" && msg.debug?.vector_status === "unavailable" && (
                <p className="mt-2 inline-flex rounded-md border border-amber-300/70 bg-amber-100/50 px-2 py-0.5 text-[11px] text-amber-900">
                  Vector DB indisponible - mode graphe
                </p>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <SourcesCollapsible sources={msg.sources} />
              )}
              {msg.role === "assistant" && msg.debug && <DebugPanel debug={msg.debug} />}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg">
              <LoadingDots />
            </div>
          </div>
        )}

        {error && (
          <div className="text-center text-sm text-accent bg-accent/10 rounded-md px-4 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t bg-card px-6 py-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about the codebase..."
            className="flex-1 rounded-md border border-input bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !input.trim()} size="icon">
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}

function MessageSquareIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  );
}
