import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { FileText, Loader2, Search } from "lucide-react";
import { api, type DocModule, type DocsSearchResult } from "@/lib/api";

export default function DocsView() {
  const [documents, setDocuments] = useState<DocModule[]>([]);
  const [modules, setModules] = useState<DocModule[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<DocsSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [related, setRelated] = useState<DocModule[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [docLoading, setDocLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDocs()
      .then((r) => {
        setDocuments(r.documents ?? []);
        setModules(r.modules);
      })
      .catch((e) => setError(e.message))
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }

    let active = true;
    setSearching(true);
    api.searchDocs(query)
      .then((r) => {
        if (active) setSearchResults(r.results);
      })
      .catch(() => {
        if (active) setSearchResults([]);
      })
      .finally(() => {
        if (active) setSearching(false);
      });

    return () => {
      active = false;
    };
  }, [search]);

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
      setRelated([]);
    } finally {
      setDocLoading(false);
    }

    if (name.endsWith(".md") && !["README.md", "INDEX.md"].includes(name)) {
      try {
        const r = await api.getRelatedDocs(name);
        setRelated(r.related);
      } catch {
        setRelated([]);
      }
    } else {
      setRelated([]);
    }
  };

  const globalDocs = documents.filter((d) => d.kind === "global");
  const sideList = search.trim().length >= 2
    ? searchResults.map((result) => ({ name: result.name, kind: result.kind }))
    : modules.map((module) => ({ name: module.name, kind: "module" }));

  return (
    <div className="flex h-screen">
      {/* Sidebar file list */}
      <div className="w-80 flex-shrink-0 border-r bg-card overflow-y-auto">
        <div className="px-4 py-3 border-b space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Modules</h2>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search docs..."
              className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        {listLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : error && modules.length === 0 ? (
          <p className="text-sm text-accent px-4 py-3">{error}</p>
        ) : (
          <div className="py-1">
            {globalDocs.length > 0 && search.trim().length < 2 && (
              <>
                <div className="px-4 pt-2 pb-1 text-xs text-muted-foreground uppercase tracking-wide">Global docs</div>
                <ul>
                  {globalDocs.map((m) => (
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
                <div className="mx-4 my-2 border-t" />
              </>
            )}

            <div className="px-4 pt-2 pb-1 text-xs text-muted-foreground uppercase tracking-wide">
              {search.trim().length >= 2 ? "Search results" : "Module docs"}
            </div>
            {searching ? (
              <div className="px-4 py-3 text-xs text-muted-foreground">Searching...</div>
            ) : (
              <ul>
                {sideList.map((m) => (
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
                      <div className="min-w-0">
                        <div className="truncate">{m.name}</div>
                        {search.trim().length >= 2 && (
                          <div className="text-xs text-muted-foreground capitalize">{m.kind}</div>
                        )}
                      </div>
                    </button>
                  </li>
                ))}
                {sideList.length === 0 && (
                  <li className="px-4 py-3 text-xs text-muted-foreground">No result</li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Doc content */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-4">
        {selected && related.length > 0 && (
          <div className="rounded-md border bg-muted/40 px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Related modules
            </div>
            <div className="flex flex-wrap gap-2">
              {related.map((item) => (
                <button
                  key={item.name}
                  onClick={() => selectModule(item.name)}
                  className="rounded-full bg-card border px-3 py-1 text-xs hover:bg-muted"
                >
                  {item.name}
                </button>
              ))}
            </div>
          </div>
        )}

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
