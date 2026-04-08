# rag/graph_context.py
import json
from pathlib import Path
from rag.retriever import RetrievedContext


class GraphContextProvider:
    def __init__(self, graph_json_path: str):
        data = json.loads(Path(graph_json_path).read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]

    def _find_node_by_label(self, label: str) -> list[dict]:
        label_lower = label.lower()
        return [n for n in self.nodes.values() if label_lower in n["label"].lower()]

    def get_context_for_chunks(self, contexts: list[RetrievedContext]) -> str:
        """
        Pour chaque chunk récupéré, cherche les relations directes
        dans le graph et les retourne sous forme textuelle.
        """
        lines = []
        seen = set()

        for ctx in contexts:
            # Chercher les noeuds correspondant au chunk
            matches = self._find_node_by_label(ctx.chunk_id.split("::")[-1])

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
