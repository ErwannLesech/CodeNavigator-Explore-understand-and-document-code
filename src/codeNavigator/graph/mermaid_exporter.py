# graph/mermaid_exporter.py
from src.codeNavigator.graph.models import Node, NodeType, EdgeType
import re


# Mapping visuel : couleur par type de noeud
NODE_STYLES = {
    NodeType.MODULE: ("[[", "]]", "fill:#1F4E79,color:#fff"),
    NodeType.CLASS: ("[", "]", "fill:#2E75B6,color:#fff"),
    NodeType.FUNCTION: ("(", ")", "fill:#BDD7EE,color:#000"),
    NodeType.METHOD: ("(", ")", "fill:#DEEAF1,color:#000"),
    NodeType.TABLE: ("[/", "/]", "fill:#375623,color:#fff"),
    NodeType.COLUMN: ("[", "]", "fill:#E2EFDA,color:#000"),
}

EDGE_LABELS = {
    EdgeType.IMPORTS: "imports",
    EdgeType.CONTAINS: "contains",
    EdgeType.INHERITS: "inherits",
    EdgeType.CALLS: "calls",
    EdgeType.READS_TABLE: "reads",
    EdgeType.WRITES_TABLE: "writes",
    EdgeType.HAS_COLUMN: "has",
    EdgeType.FOREIGN_KEY: "FK",
    EdgeType.DEPENDS_ON: "depends_on",
}


def _safe_id(node_id: str) -> str:
    """Mermaid n'accepte pas les caract�res sp�ciaux dans les IDs."""
    return (
        node_id.replace("::", "__")
        .replace("\\", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def _safe_filename(value: str) -> str:
    """Cr�e un segment de nom de fichier s�r sur tous les OS."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return safe.replace(".", "_").strip("_") or "unknown"


def _node_label(node: Node) -> str:
    open_b, close_b, _ = NODE_STYLES.get(node.node_type, ("[", "]", ""))
    return f'{_safe_id(node.node_id)}{open_b}"{node.label}"{close_b}'


def generate_module_dependency_diagram(
    nodes: dict[str, Node], edges: list, max_nodes: int = 40
) -> str:
    """
    Diagramme de d�pendances entre modules (imports uniquement).
    Limit� aux noeuds internes (pas les d�pendances externes).
    """
    lines = ["flowchart TD", "    %% Module dependency diagram"]

    module_nodes = {
        nid: n
        for nid, n in nodes.items()
        if n.node_type == NodeType.MODULE and not n.metadata.get("external", False)
    }

    # Limiter si trop de modules
    selected = dict(list(module_nodes.items())[:max_nodes])

    # Styles
    for nid, node in selected.items():
        _, _, style = NODE_STYLES[NodeType.MODULE]
        lines.append(f"    style {_safe_id(nid)} {style}")

    # Noeuds
    for nid, node in selected.items():
        lines.append(f"    {_node_label(node)}")

    # Ar�tes IMPORTS uniquement entre modules internes
    for edge in edges:
        if (
            edge.edge_type == EdgeType.IMPORTS
            and edge.source in selected
            and edge.target in selected
        ):
            src = _safe_id(edge.source)
            tgt = _safe_id(edge.target)
            lines.append(f"    {src} -->|imports| {tgt}")

    return "\n".join(lines)


def generate_class_diagram(
    nodes: dict[str, Node], edges: list, file_filter: str | None = None
) -> str:
    """
    Diagramme classes/m�thodes pour un module donn�.
    file_filter : si fourni, limite au fichier sp�cifi�.
    """
    lines = ["flowchart TD", "    %% Class diagram"]

    relevant_types = {NodeType.CLASS, NodeType.METHOD, NodeType.FUNCTION}

    selected = {
        nid: n
        for nid, n in nodes.items()
        if n.node_type in relevant_types
        and not n.metadata.get("external", False)
        and (file_filter is None or n.metadata.get("file", "") == file_filter)
    }

    for nid, node in selected.items():
        _, _, style = NODE_STYLES[node.node_type]
        lines.append(f"    style {_safe_id(nid)} {style}")
        lines.append(f"    {_node_label(node)}")

    for edge in edges:
        if edge.source in selected and edge.target in selected:
            src = _safe_id(edge.source)
            tgt = _safe_id(edge.target)
            arrow = "-->" if edge.edge_type != EdgeType.INHERITS else "-.->|inherits|"
            lines.append(f"    {src} {arrow} {tgt}")

    return "\n".join(lines)


def generate_erd(nodes: dict[str, Node], edges: list) -> str:
    """
    Diagramme ERD Mermaid depuis les tables SQL et leurs relations.
    Utilise la syntaxe erDiagram native de Mermaid.
    """
    lines = ["erDiagram"]

    table_nodes = {
        nid: n
        for nid, n in nodes.items()
        if n.node_type == NodeType.TABLE and not n.metadata.get("external", False)
    }
    column_nodes = {
        nid: n for nid, n in nodes.items() if n.node_type == NodeType.COLUMN
    }

    # D�finition des tables avec colonnes
    for table_id, table_node in table_nodes.items():
        lines.append(f"    {table_node.label} {{")
        for edge in edges:
            if edge.edge_type == EdgeType.HAS_COLUMN and edge.source == table_id:
                col = column_nodes.get(edge.target)
                if col:
                    col_type = col.metadata.get("type", "string").replace(" ", "_")
                    pk_marker = " PK" if col.metadata.get("primary_key") else ""
                    lines.append(f"        {col_type} {col.label}{pk_marker}")
        lines.append("    }")

    # Relations FK
    for edge in edges:
        if edge.edge_type == EdgeType.FOREIGN_KEY:
            src = nodes.get(edge.source)
            tgt = nodes.get(edge.target)
            if src and tgt:
                lines.append(
                    f'    {src.label} ||--o{{ {tgt.label} : "{edge.metadata.get("column", "FK")}"'
                )

    return "\n".join(lines)


def generate_sql_lineage_diagram(nodes: dict[str, Node], edges: list) -> str:
    """Diagramme orient� impact SQL entre tables (amont -> aval)."""
    lines = ["flowchart LR", "    %% SQL lineage diagram"]

    table_nodes = {
        nid: n
        for nid, n in nodes.items()
        if n.node_type == NodeType.TABLE and not n.metadata.get("external", False)
    }

    for nid, node in table_nodes.items():
        _, _, style = NODE_STYLES[NodeType.TABLE]
        lines.append(f"    style {_safe_id(nid)} {style}")
        lines.append(f"    {_node_label(node)}")

    for edge in edges:
        if (
            edge.edge_type == EdgeType.DEPENDS_ON
            and edge.source in table_nodes
            and edge.target in table_nodes
        ):
            src = _safe_id(edge.source)
            tgt = _safe_id(edge.target)
            lines.append(f"    {src} -->|feeds| {tgt}")

    return "\n".join(lines)


def export_all_diagrams(
    nodes: dict[str, Node], edges: list, output_dir: str
) -> dict[str, str]:
    """G�n�re et �crit tous les diagrammes, retourne un dict nom -> contenu."""
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    diagrams = {}

    # 1. D�pendances entre modules
    dep_diagram = generate_module_dependency_diagram(nodes, edges)
    (out / "module_dependencies.mermaid").write_text(dep_diagram, encoding="utf-8")
    diagrams["module_dependencies"] = dep_diagram

    # 2. ERD SQL (si des tables existent)
    table_nodes = [n for n in nodes.values() if n.node_type == NodeType.TABLE]
    if table_nodes:
        erd = generate_erd(nodes, edges)
        (out / "erd.mermaid").write_text(erd, encoding="utf-8")
        diagrams["erd"] = erd

        lineage = generate_sql_lineage_diagram(nodes, edges)
        (out / "sql_lineage.mermaid").write_text(lineage, encoding="utf-8")
        diagrams["sql_lineage"] = lineage

    # 3. Un diagramme de classes par fichier Python
    python_files = list(
        {
            file_path
            for n in nodes.values()
            if n.node_type in {NodeType.CLASS, NodeType.FUNCTION}
            for file_path in [n.metadata.get("file")]
            if isinstance(file_path, str) and file_path
        }
    )
    for file_path in python_files:
        safe = _safe_filename(file_path)
        diagram = generate_class_diagram(nodes, edges, file_filter=file_path)
        (out / f"classes_{safe}.mermaid").write_text(diagram, encoding="utf-8")
        diagrams[f"classes_{safe}"] = diagram

    return diagrams



