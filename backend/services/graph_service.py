from __future__ import annotations

import json

from backend.config import GRAPH_JSON_PATH
from backend.schemas import DocModule, GraphResponse
from backend.services.docs_service import (
    extract_doc_links_from_index,
    normalize_path,
)


def read_graph() -> GraphResponse:
    payload = json.loads(GRAPH_JSON_PATH.read_text(encoding="utf-8"))

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", payload.get("links", []))

    return GraphResponse(nodes=nodes, edges=edges)


def related_docs(module_name: str) -> list[DocModule]:
    graph = read_graph()
    mapping = extract_doc_links_from_index()
    reverse_mapping = {
        doc_name: source_path for source_path, doc_name in mapping.items()
    }

    if module_name not in reverse_mapping:
        return []

    raw_source = reverse_mapping[module_name]
    module_node = next(
        (
            node
            for node in graph.nodes
            if node.get("type") == "module"
            and normalize_path(str(node.get("label", ""))) == raw_source
        ),
        None,
    )
    if not module_node:
        return []

    module_id = str(module_node.get("id", ""))
    neighbor_module_labels: set[str] = set()
    for edge in graph.edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source == module_id or target == module_id:
            other_id = target if source == module_id else source
            other_node = next(
                (node for node in graph.nodes if str(node.get("id", "")) == other_id),
                None,
            )
            if other_node and other_node.get("type") == "module":
                neighbor_module_labels.add(
                    normalize_path(str(other_node.get("label", "")))
                )

    related: list[DocModule] = []
    for raw in sorted(neighbor_module_labels):
        doc_name = mapping.get(raw)
        if doc_name:
            related.append(
                DocModule(
                    name=doc_name,
                    path=f"modules/{doc_name}",
                    kind="module",
                    source_path=raw,
                )
            )
    return related
