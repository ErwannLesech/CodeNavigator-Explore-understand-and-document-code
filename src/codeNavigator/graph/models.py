from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    TABLE = "table"
    COLUMN = "column"


class EdgeType(str, Enum):
    IMPORTS = "imports"  # module A importe module B
    CONTAINS = "contains"  # module contient classe/fonction
    INHERITS = "inherits"  # classe h�rite de classe
    CALLS = "calls"  # fonction appelle fonction (best-effort)
    READS_TABLE = "reads_table"  # requ�te lit une table
    WRITES_TABLE = "writes_table"  # requ�te �crit dans une table
    HAS_COLUMN = "has_column"  # table a une colonne
    FOREIGN_KEY = "foreign_key"  # colonne r�f�rence une autre table
    DEPENDS_ON = "depends_on"  # table cible d�pend d'une table source


@dataclass
class Node:
    node_id: str
    node_type: NodeType
    label: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    edge_type: EdgeType
    metadata: dict = field(default_factory=dict)
