# rag/graph_context.py
import json
from pathlib import Path
from rag.retriever import RetrievedContext


class GraphContextProvider:
    def __init__(self, graph_json_path: str):
        data = json.loads(Path(graph_json_path).read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]
        self._table_nodes_by_label = {
            n["label"].lower(): n
            for n in self.nodes.values()
            if n.get("type") == "table" and isinstance(n.get("label"), str)
        }
        self._module_nodes_by_path = {
            self._normalize_path(n["label"]): n
            for n in self.nodes.values()
            if n.get("type") == "module" and isinstance(n.get("label"), str)
        }

    def _normalize_path(self, value: str) -> str:
        return value.replace("\\", "/").strip().lower()

    def _find_node_by_label(self, label: str) -> list[dict]:
        label_lower = label.lower()
        return [n for n in self.nodes.values() if label_lower in n["label"].lower()]

    def _find_nodes_for_context(self, ctx: RetrievedContext) -> list[dict]:
        matches: list[dict] = []
        seen_ids: set[str] = set()

        def _add(node: dict | None) -> None:
            if not node:
                return
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id not in seen_ids:
                seen_ids.add(node_id)
                matches.append(node)

        if isinstance(ctx.source_file, str):
            _add(self._module_nodes_by_path.get(self._normalize_path(ctx.source_file)))

        if ctx.chunk_type == "table_schema":
            table_name = ctx.metadata.get("table_name")
            if isinstance(table_name, str):
                _add(self._table_nodes_by_label.get(table_name.lower()))

        if ctx.chunk_type == "sql_query":
            for key in ("tables_read", "tables_written"):
                for table_name in ctx.metadata.get(key, []) or []:
                    if isinstance(table_name, str):
                        _add(self._table_nodes_by_label.get(table_name.lower()))

        if not matches:
            for node in self._find_node_by_label(ctx.chunk_id.split("::")[-1])[:2]:
                _add(node)

        return matches

    def get_context_for_chunks(self, contexts: list[RetrievedContext]) -> str:
        """
        Pour chaque chunk récupéré, cherche les relations directes
        dans le graph et les retourne sous forme textuelle.
        """
        lines = []
        seen = set()

        for ctx in contexts:
            matches = self._find_nodes_for_context(ctx)

            for node in matches[:2]:  # max 2 noeuds par chunk
                node_id = node["id"]
                if node_id in seen:
                    continue
                seen.add(node_id)

                # Relations sortantes
                outgoing = [e for e in self.edges if e["source"] == node_id]
                # Relations entrantes
                incoming = [e for e in self.edges if e["target"] == node_id]

                if outgoing or incoming:
                    lines.append(f"Node: {node['label']} ({node['type']})")
                    for e in outgoing[:4]:
                        target = self.nodes.get(e["target"], {})
                        lines.append(
                            f"  --> {e['type']} --> {target.get('label', e['target'])}"
                        )
                    for e in incoming[:4]:
                        source = self.nodes.get(e["source"], {})
                        lines.append(
                            f"  <-- {e['type']} <-- {source.get('label', e['source'])}"
                        )

        return "\n".join(lines) if lines else ""
