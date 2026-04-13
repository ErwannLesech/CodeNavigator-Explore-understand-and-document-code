import { useEffect, useMemo, useState, type ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileText,
  Folder,
  Loader2,
  Search,
} from "lucide-react";
import { api, type DocModule, type DocsSearchResult } from "@/lib/api";

type RepoTreeNode = {
  name: string;
  fullPath: string;
  moduleName?: string;
  children: RepoTreeNode[];
};

function normalizeMarkdownContent(rawContent: string): string {
  let content = rawContent.trim();

  const unwrappedMarkdownFences = content.replace(
    /```(?:markdown|md)\s*\n([\s\S]*?)```/gi,
    "$1",
  );

  if (unwrappedMarkdownFences !== content) {
    content = unwrappedMarkdownFences.trim();
  }

  const fullyWrappedMatch = content.match(/^```[\w-]*\s*\n([\s\S]*?)\n```$/);
  if (fullyWrappedMatch && /(^|\n)\s*#{1,6}\s+/.test(fullyWrappedMatch[1])) {
    content = fullyWrappedMatch[1].trim();
  }

  return content;
}

function normalizeDocLinkToName(href?: string): string | null {
  if (!href) {
    return null;
  }

  const raw = href.split("#")[0].split("?")[0].replace(/\\/g, "/").trim();
  if (!raw || /^https?:\/\//i.test(raw)) {
    return null;
  }

  const modulesMatch = raw.match(/(?:^|\/)modules\/([^/]+\.md)$/i);
  if (modulesMatch) {
    return decodeURIComponent(modulesMatch[1]);
  }

  const docMatch = raw.match(/(?:^|\/)(README\.md|INDEX\.md)$/i);
  if (docMatch) {
    const name = docMatch[1].toUpperCase();
    return name === "README.MD" ? "README.md" : "INDEX.md";
  }

  const fileName = raw.split("/").at(-1);
  if (fileName?.toLowerCase().endsWith(".md")) {
    return decodeURIComponent(fileName);
  }

  return null;
}

function buildRepoTree(modules: DocModule[]): RepoTreeNode[] {
  const roots: RepoTreeNode[] = [];

  const upsertChild = (children: RepoTreeNode[], name: string, fullPath: string) => {
    const existing = children.find((child) => child.name === name && !child.moduleName);
    if (existing) {
      return existing;
    }
    const node: RepoTreeNode = { name, fullPath, children: [] };
    children.push(node);
    children.sort((a, b) => a.name.localeCompare(b.name));
    return node;
  };

  for (const module of modules) {
    const source = (module.source_path ?? module.name).replace(/\\/g, "/");
    const parts = source.split("/").filter(Boolean);
    if (parts.length === 0) {
      continue;
    }

    let level = roots;
    let prefix = "";
    for (let index = 0; index < parts.length - 1; index += 1) {
      const part = parts[index];
      prefix = prefix ? `${prefix}/${part}` : part;
      const folder = upsertChild(level, part, prefix);
      level = folder.children;
    }

    const leafName = parts[parts.length - 1];
    const leafPath = prefix ? `${prefix}/${leafName}` : leafName;
    level.push({ name: leafName, fullPath: leafPath, moduleName: module.name, children: [] });
    level.sort((a, b) => {
      if (!!a.moduleName === !!b.moduleName) {
        return a.name.localeCompare(b.name);
      }
      return a.moduleName ? 1 : -1;
    });
  }

  return roots;
}

export default function DocsView() {
  const [documents, setDocuments] = useState<DocModule[]>([]);
  const [modules, setModules] = useState<DocModule[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<DocsSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [related, setRelated] = useState<DocModule[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
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

  const knownDocNames = useMemo(
    () => new Set(documents.map((doc) => doc.name)),
    [documents],
  );
  const repoTree = useMemo(() => buildRepoTree(modules), [modules]);

  useEffect(() => {
    setExpandedFolders(new Set(repoTree.map((node) => node.fullPath)));
  }, [repoTree]);

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
        if (active) {
          setSearchResults(r.results);
        }
      })
      .catch(() => {
        if (active) {
          setSearchResults([]);
        }
      })
      .finally(() => {
        if (active) {
          setSearching(false);
        }
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
      setContent(normalizeMarkdownContent(r.content));
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load document";
      setError(message);
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

  const toggleFolder = (path: string) => {
    setExpandedFolders((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderTreeNode = (node: RepoTreeNode, depth = 0) => {
    const isFolder = !node.moduleName;
    const isExpanded = expandedFolders.has(node.fullPath);

    if (isFolder) {
      return (
        <li key={node.fullPath}>
          <button
            onClick={() => toggleFolder(node.fullPath)}
            className="w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors text-foreground hover:bg-muted"
            style={{ paddingLeft: `${16 + depth * 14}px` }}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 flex-shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 flex-shrink-0 text-muted-foreground" />
            )}
            <Folder className="w-4 h-4 flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{node.name}</span>
          </button>
          {isExpanded && node.children.length > 0 && (
            <ul>{node.children.map((child) => renderTreeNode(child, depth + 1))}</ul>
          )}
        </li>
      );
    }

    return (
      <li key={node.fullPath}>
        <button
          onClick={() => node.moduleName && selectModule(node.moduleName)}
          className={`w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
            selected === node.moduleName
              ? "bg-primary/10 text-primary font-medium"
              : "text-foreground hover:bg-muted"
          }`}
          style={{ paddingLeft: `${16 + depth * 14}px` }}
        >
          <FileCode2 className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">{node.name}</span>
        </button>
      </li>
    );
  };

  const globalDocs = documents.filter((doc) => doc.kind === "global");
  const sideList = search.trim().length >= 2
    ? searchResults.map((result) => ({
      name: result.name,
      kind: result.kind,
      sourcePath: result.source_path,
    }))
    : [];

  return (
    <div className="flex h-screen">
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
                  {globalDocs.map((doc) => (
                    <li key={doc.name}>
                      <button
                        onClick={() => selectModule(doc.name)}
                        className={`w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                          selected === doc.name
                            ? "bg-primary/10 text-primary font-medium"
                            : "text-foreground hover:bg-muted"
                        }`}
                      >
                        <FileText className="w-4 h-4 flex-shrink-0" />
                        <span className="truncate">{doc.name}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="mx-4 my-2 border-t" />
              </>
            )}

            <div className="px-4 pt-2 pb-1 text-xs text-muted-foreground uppercase tracking-wide">
              {search.trim().length >= 2 ? "Search results" : "Repository tree"}
            </div>
            {search.trim().length >= 2 ? (
              searching ? (
                <div className="px-4 py-3 text-xs text-muted-foreground">Searching...</div>
              ) : (
                <ul>
                  {sideList.map((item) => (
                    <li key={item.name}>
                      <button
                        onClick={() => selectModule(item.name)}
                        className={`w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                          selected === item.name
                            ? "bg-primary/10 text-primary font-medium"
                            : "text-foreground hover:bg-muted"
                        }`}
                      >
                        <FileText className="w-4 h-4 flex-shrink-0" />
                        <div className="min-w-0">
                          <div className="truncate">{item.sourcePath ?? item.name}</div>
                          <div className="text-xs text-muted-foreground capitalize">{item.kind}</div>
                        </div>
                      </button>
                    </li>
                  ))}
                  {sideList.length === 0 && (
                    <li className="px-4 py-3 text-xs text-muted-foreground">No result</li>
                  )}
                </ul>
              )
            ) : (
              <ul>{repoTree.map((node) => renderTreeNode(node))}</ul>
            )}
          </div>
        )}
      </div>

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
                  {item.source_path ?? item.name}
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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children, ...props }: ComponentProps<"a">) => {
                  const docName = normalizeDocLinkToName(href);
                  if (docName && knownDocNames.has(docName)) {
                    return (
                      <button
                        type="button"
                        onClick={() => selectModule(docName)}
                        className="text-primary underline underline-offset-2 hover:text-primary/80"
                      >
                        {children}
                      </button>
                    );
                  }

                  return (
                    <a href={href} {...props} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
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
