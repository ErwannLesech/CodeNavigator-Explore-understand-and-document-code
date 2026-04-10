# graph/json_exporter.py
import json
from pathlib import Path
from src.codeNavigator.graph.models import Node, Edge


def export_graph_json(
    nodes: dict[str, Node], edges: list[Edge], output_path: str
) -> dict:
    serialized_nodes = []
    for n in nodes.values():
        metadata = dict(n.metadata)
        if "type" in metadata:
            metadata["data_type"] = metadata.pop("type")
        serialized_nodes.append(
            {"id": n.node_id, "type": n.node_type.value, "label": n.label, **metadata}
        )

    data = {
        "nodes": serialized_nodes,
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "type": e.edge_type.value,
                **e.metadata,
            }
            for e in edges
        ],
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_types": {
                t: sum(1 for n in nodes.values() if n.node_type.value == t)
                for t in set(n.node_type.value for n in nodes.values())
            },
        },
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

