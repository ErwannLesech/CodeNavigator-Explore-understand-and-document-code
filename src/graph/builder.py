# graph/builder.py
import re
import networkx as nx
from src.ingestion.parser_dispatcher import ParsedFile
from src.ingestion.python_parser import ModuleInfo
from src.ingestion.sql_parser import SqlFileInfo
from src.graph.models import Node, Edge, NodeType, EdgeType


class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._edge_keys: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _add_node(self, node: Node):
        self._nodes[node.node_id] = node
        self.graph.add_node(
            node.node_id,
            label=node.label,
            node_type=node.node_type.value,
            **node.metadata,
        )

    def _add_edge(self, edge: Edge):
        key = (edge.source, edge.target, edge.edge_type.value)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append(edge)
        self.graph.add_edge(
            edge.source, edge.target, edge_type=edge.edge_type.value, **edge.metadata
        )

    def _node_exists(self, node_id: str) -> bool:
        return node_id in self._nodes

    # ------------------------------------------------------------------ #
    # Python
    # ------------------------------------------------------------------ #

    def _ingest_python(self, info: ModuleInfo, file_path: str):
        module_id = f"module::{file_path}"

        self._add_node(
            Node(
                node_id=module_id,
                node_type=NodeType.MODULE,
                label=file_path,
                metadata={"docstring": info.docstring or ""},
            )
        )

        # Résolution des imports vers d'autres modules du projet
        for imp in info.imports:
            # Extraire le nom du module importé
            # "from src.ingestion.parser_dispatcher import ParsedFile" -> "ingestion/parser_dispatcher.py"
            match = re.match(r"(?:from|import)\s+([\w.]+)", imp)
            if match:
                imported = match.group(1).replace(".", "/") + ".py"
                imported_id = f"module::{imported}"
                # On crée un noeud placeholder si le module cible n'existe pas encore
                if not self._node_exists(imported_id):
                    self._add_node(
                        Node(
                            node_id=imported_id,
                            node_type=NodeType.MODULE,
                            label=imported,
                            metadata={"external": True},
                        )
                    )
                self._add_edge(
                    Edge(
                        source=module_id, target=imported_id, edge_type=EdgeType.IMPORTS
                    )
                )

        # Fonctions top-level
        for func in info.functions:
            func_id = f"function::{file_path}::{func.name}"
            self._add_node(
                Node(
                    node_id=func_id,
                    node_type=NodeType.FUNCTION,
                    label=func.name,
                    metadata={
                        "file": file_path,
                        "lineno": func.lineno,
                        "args": func.args,
                        "has_docstring": func.docstring is not None,
                        "docstring": func.docstring or "",
                    },
                )
            )
            self._add_edge(
                Edge(source=module_id, target=func_id, edge_type=EdgeType.CONTAINS)
            )

        # Classes + méthodes
        for cls in info.classes:
            class_id = f"class::{file_path}::{cls.name}"
            self._add_node(
                Node(
                    node_id=class_id,
                    node_type=NodeType.CLASS,
                    label=cls.name,
                    metadata={
                        "file": file_path,
                        "lineno": cls.lineno,
                        "has_docstring": cls.docstring is not None,
                        "docstring": cls.docstring or "",
                    },
                )
            )
            self._add_edge(
                Edge(source=module_id, target=class_id, edge_type=EdgeType.CONTAINS)
            )

            # Héritage
            for base in cls.bases:
                base_id = f"class::external::{base}"
                if not self._node_exists(base_id):
                    self._add_node(
                        Node(
                            node_id=base_id,
                            node_type=NodeType.CLASS,
                            label=base,
                            metadata={"external": True},
                        )
                    )
                self._add_edge(
                    Edge(source=class_id, target=base_id, edge_type=EdgeType.INHERITS)
                )

            # Méthodes
            for method in cls.methods:
                method_id = f"method::{file_path}::{cls.name}::{method.name}"
                self._add_node(
                    Node(
                        node_id=method_id,
                        node_type=NodeType.METHOD,
                        label=f"{cls.name}.{method.name}",
                        metadata={
                            "file": file_path,
                            "lineno": method.lineno,
                            "args": method.args,
                            "has_docstring": method.docstring is not None,
                        },
                    )
                )
                self._add_edge(
                    Edge(source=class_id, target=method_id, edge_type=EdgeType.CONTAINS)
                )

    # ------------------------------------------------------------------ #
    # SQL
    # ------------------------------------------------------------------ #

    def _ingest_sql(self, info: SqlFileInfo, file_path: str):
        module_id = f"module::{file_path}"

        if not self._node_exists(module_id):
            self._add_node(
                Node(
                    node_id=module_id,
                    node_type=NodeType.MODULE,
                    label=file_path,
                    metadata={},
                )
            )

        # Tables et colonnes
        for schema in info.schemas:
            table_id = f"table::{schema.name}"
            self._add_node(
                Node(
                    node_id=table_id,
                    node_type=NodeType.TABLE,
                    label=schema.name,
                    metadata={
                        "file": file_path,
                        "column_count": len(schema.columns),
                        "primary_keys": schema.primary_keys,
                    },
                )
            )

            for col in schema.columns:
                col_id = f"column::{schema.name}::{col['name']}"
                self._add_node(
                    Node(
                        node_id=col_id,
                        node_type=NodeType.COLUMN,
                        label=col["name"],
                        metadata={
                            "type": col["type"],
                            "nullable": col["nullable"],
                            "primary_key": col["primary_key"],
                        },
                    )
                )
                self._add_edge(
                    Edge(source=table_id, target=col_id, edge_type=EdgeType.HAS_COLUMN)
                )

            # Foreign keys
            for fk in schema.foreign_keys:
                ref_table_id = f"table::{fk['references_table']}"
                if not self._node_exists(ref_table_id):
                    self._add_node(
                        Node(
                            node_id=ref_table_id,
                            node_type=NodeType.TABLE,
                            label=fk["references_table"],
                            metadata={"external": True},
                        )
                    )
                self._add_edge(
                    Edge(
                        source=table_id,
                        target=ref_table_id,
                        edge_type=EdgeType.FOREIGN_KEY,
                        metadata={
                            "column": fk["column"],
                            "references_column": fk["references_column"],
                        },
                    )
                )

        # Lineage des requétes
        for query in info.queries:
            read_tables: list[str] = []
            written_tables: list[str] = []

            for table_ref in query.tables_read:
                table_id = f"table::{table_ref.name}"
                if not self._node_exists(table_id):
                    self._add_node(
                        Node(
                            node_id=table_id,
                            node_type=NodeType.TABLE,
                            label=table_ref.name,
                        )
                    )
                read_tables.append(table_id)
                self._add_edge(
                    Edge(
                        source=module_id,
                        target=table_id,
                        edge_type=EdgeType.READS_TABLE,
                    )
                )
            for table_ref in query.tables_written:
                table_id = f"table::{table_ref.name}"
                if not self._node_exists(table_id):
                    self._add_node(
                        Node(
                            node_id=table_id,
                            node_type=NodeType.TABLE,
                            label=table_ref.name,
                        )
                    )
                written_tables.append(table_id)
                self._add_edge(
                    Edge(
                        source=module_id,
                        target=table_id,
                        edge_type=EdgeType.WRITES_TABLE,
                    )
                )

            # Impact table -> table : toutes les sources alimentant toutes les cibles écrites.
            for src_table in read_tables:
                for dst_table in written_tables:
                    if src_table == dst_table:
                        continue
                    self._add_edge(
                        Edge(
                            source=src_table,
                            target=dst_table,
                            edge_type=EdgeType.DEPENDS_ON,
                            metadata={
                                "via": file_path,
                                "query_type": query.query_type,
                            },
                        )
                    )

    # ------------------------------------------------------------------ #
    # Point d'entrée
    # ------------------------------------------------------------------ #

    def ingest(self, parsed_files: list[ParsedFile]) -> nx.DiGraph:
        for parsed in parsed_files:
            file_path = parsed.source_file.relative_path
            if parsed.python_info:
                self._ingest_python(parsed.python_info, file_path)
            if parsed.sql_info:
                self._ingest_sql(parsed.sql_info, file_path)

        return self.graph

    def get_nodes(self) -> dict[str, Node]:
        return self._nodes

    def get_edges(self) -> list[Edge]:
        return self._edges
