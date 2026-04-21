import json
from pathlib import Path

from src.graph.json_exporter import export_graph_json
from src.graph.models import Edge, EdgeType, Node, NodeType


def test_export_graph_json_serializes_nodes_edges_and_stats(tmp_path: Path) -> None:
    output_path = tmp_path / "graph.json"
    nodes = {
        "class-node": Node(
            node_id="class-node",
            node_type=NodeType.CLASS,
            label="User",
            metadata={"type": "python", "owner": "team-a"},
        ),
        "function-node": Node(
            node_id="function-node",
            node_type=NodeType.FUNCTION,
            label="helper",
        ),
    }
    edges = [
        Edge(
            source="class-node",
            target="function-node",
            edge_type=EdgeType.CONTAINS,
            metadata={"weight": 1},
        )
    ]

    data = export_graph_json(nodes, edges, str(output_path))

    assert output_path.exists()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == data

    assert data["stats"]["node_count"] == 2
    assert data["stats"]["edge_count"] == 1
    assert data["stats"]["node_types"]["class"] == 1
    assert data["stats"]["node_types"]["function"] == 1

    class_node = next(node for node in data["nodes"] if node["id"] == "class-node")
    assert class_node["type"] == "class"
    assert class_node["data_type"] == "python"
    assert class_node["owner"] == "team-a"

    edge = data["edges"][0]
    assert edge["source"] == "class-node"
    assert edge["target"] == "function-node"
    assert edge["type"] == "contains"
    assert edge["weight"] == 1
