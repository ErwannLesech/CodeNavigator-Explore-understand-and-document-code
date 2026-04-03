# ingestion/treesitter_parser.py
from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

# tree-sitter-languages est un bundle qui évite de compiler les grammaires manuellement
# pip install tree-sitter==0.21.3 tree-sitter-languages==1.10.2
try:
    from tree_sitter_languages import get_language, get_parser
    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False


@dataclass
class TSNode:
    """Représentation simplifiée d'un noeud AST."""
    node_type: str
    text: str
    start_line: int
    end_line: int
    children: list["TSNode"] = field(default_factory=list)


@dataclass
class ParsedUnit:
    """Unité syntaxique extraite : fonction, classe, ou bloc générique."""
    unit_type: str           # "function", "class", "method", "import"
    name: str
    language: str
    start_line: int
    end_line: int
    source: str              # code source brut de l'unité
    docstring: Optional[str] = None
    parent_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class TreeSitterResult:
    language: str
    source_file: str
    units: list[ParsedUnit]
    raw_tree_summary: str    # résumé textuel de l'AST pour debug


def _get_node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _extract_docstring_python(node, source_bytes: bytes) -> Optional[str]:
    """Cherche le premier string littéral dans le corps d'une fonction/classe Python."""
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            raw = _get_node_text(expr, source_bytes)
                            return raw.strip('"""').strip("'''").strip('"').strip("'").strip()
    return None


def _parse_python(tree, source_bytes: bytes, source_file: str) -> list[ParsedUnit]:
    units = []
    root = tree.root_node

    def visit(node, parent_class: Optional[str] = None):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source_bytes) if name_node else "unknown"
            docstring = _extract_docstring_python(node, source_bytes)
            units.append(ParsedUnit(
                unit_type="method" if parent_class else "function",
                name=name,
                language="python",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_get_node_text(node, source_bytes),
                docstring=docstring,
                parent_name=parent_class,
                metadata={}
            ))
            # Pas de récursion dans les fonctions imbriquées pour rester propre

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source_bytes) if name_node else "unknown"
            docstring = _extract_docstring_python(node, source_bytes)
            units.append(ParsedUnit(
                unit_type="class",
                name=name,
                language="python",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_get_node_text(node, source_bytes),
                docstring=docstring,
                metadata={}
            ))
            for child in node.children:
                visit(child, parent_class=name)
            return  # on a déjà visité les enfants

        for child in node.children:
            visit(child, parent_class)

    visit(root)
    return units


def _parse_javascript(tree, source_bytes: bytes, source_file: str) -> list[ParsedUnit]:
    """Parser JS/TS — extrait les fonctions et classes."""
    units = []
    root = tree.root_node

    FUNCTION_TYPES = {
        "function_declaration",
        "function",
        "arrow_function",
        "method_definition"
    }

    def visit(node, parent_class: Optional[str] = None):
        if node.type in FUNCTION_TYPES:
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source_bytes) if name_node else "<anonymous>"
            units.append(ParsedUnit(
                unit_type="method" if parent_class else "function",
                name=name,
                language="javascript",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_get_node_text(node, source_bytes),
                parent_name=parent_class,
            ))

        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source_bytes) if name_node else "unknown"
            units.append(ParsedUnit(
                unit_type="class",
                name=name,
                language="javascript",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=_get_node_text(node, source_bytes),
            ))
            for child in node.children:
                visit(child, parent_class=name)
            return

        for child in node.children:
            visit(child, parent_class)

    visit(root)
    return units


# Mapping langage -> fonction de parsing spécialisée
LANGUAGE_PARSERS = {
    "python": _parse_python,
    "javascript": _parse_javascript,
    "typescript": _parse_javascript,  # la grammaire TS est quasi identique
}


def parse_with_treesitter(source: str, language: str, source_file: str) -> Optional[TreeSitterResult]:
    """
    Point d'entrée principal. Retourne None si tree-sitter n'est pas disponible
    ou si le langage n'est pas supporté.
    """
    if not TREESITTER_AVAILABLE:
        return None
    if language not in LANGUAGE_PARSERS:
        return None

    try:
        parser = get_parser(language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        units = LANGUAGE_PARSERS[language](tree, source_bytes, source_file)

        return TreeSitterResult(
            language=language,
            source_file=source_file,
            units=units,
            raw_tree_summary=f"root: {tree.root_node.type}, children: {len(tree.root_node.children)}"
        )
    except Exception as e:
        # Ne pas faire crasher le pipeline si un fichier pose problème
        return None