import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { FileText, Loader2 } from "lucide-react";
import { api, type DocModule } from "@/lib/api";

export default function DocsView() {
  const [modules, setModules] = useState<DocModule[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [listLoading, setListLoading] = useState(true);
  const [docLoading, setDocLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDocs()
      .then((r) => setModules(r.modules))
      .catch((e) => setError(e.message))
      .finally(() => setListLoading(false));
  }, []);

  const selectModule = async (name: string) => {
    setSelected(name);
    setDocLoading(true);
    setError(null);
    try {
      const r = await api.getDoc(name);
      setContent(r.content);
    } catch (e: any) {
      setError(e.message);
      setContent("");
    } finally {
      setDocLoading(false);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar file list */}
      <div className="w-64 flex-shrink-0 border-r bg-card overflow-y-auto">
        <div className="px-4 py-3 border-b">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Modules</h2>
        </div>
        {listLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : error && modules.length === 0 ? (
          <p className="text-sm text-accent px-4 py-3">{error}</p>
        ) : (
          <ul className="py-1">
            {modules.map((m) => (
              <li key={m.name}>
                <button
                  onClick={() => selectModule(m.name)}
                  className={`w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    selected === m.name
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-foreground hover:bg-muted"
                  }`}
                >
                  <FileText className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">{m.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Doc content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {docLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : error && selected ? (
          <div className="text-accent text-sm">{error}</div>
        ) : content ? (
          <article className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:font-mono prose-pre:bg-muted prose-pre:rounded-lg">
            <ReactMarkdown>{content}</ReactMarkdown>
          </article>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">Select a module to view its documentation</p>
          </div>
        )}
      </div>
    </div>
  );
}
