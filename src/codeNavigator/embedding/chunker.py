# embedding/chunker.py
from dataclasses import dataclass, field
from typing import Optional
from src.codeNavigator.ingestion.parser_dispatcher import ParsedFile
from src.codeNavigator.ingestion.python_parser import FunctionInfo, ClassInfo
from src.codeNavigator.ingestion.sql_parser import TableSchema, QueryInfo


@dataclass
class Chunk:
    """Unit� minimale indexable."""

    chunk_id: str  # identifiant unique : "path/to/file.py::MyClass::my_method"
    content: str  # texte qui sera embed�
    chunk_type: (
        str  # "function" | "class" | "method" | "table_schema" | "sql_query" | "module"
    )
    language: str
    source_file: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: dict = field(default_factory=dict)


def _build_id(*parts: Optional[str]) -> str:
    return "::".join(p for p in parts if p)


def _format_function(
    func: FunctionInfo, file_path: str, parent: Optional[str] = None
) -> Chunk:
    """Formate une fonction/m�thode en texte enrichi pour l'embedding."""
    args_str = ", ".join(func.args)
    lines = [
        f"{'Method' if func.is_method else 'Function'}: {func.name}",
        f"File: {file_path}",
    ]
    if parent:
        lines.append(f"Class: {parent}")
    if func.decorators:
        lines.append(f"Decorators: {', '.join(func.decorators)}")
    lines.append(f"Arguments: ({args_str})")
    if func.docstring:
        lines.append(f"Docstring: {func.docstring}")

    return Chunk(
        chunk_id=_build_id(file_path, parent, func.name),
        content="\n".join(lines),
        chunk_type="method" if func.is_method else "function",
        language="python",
        source_file=file_path,
        start_line=func.lineno,
        metadata={
            "name": func.name,
            "parent_class": parent,
            "has_docstring": func.docstring is not None,
            "decorators": func.decorators,
            "args": func.args,
        },
    )


def _format_class(cls: ClassInfo, file_path: str) -> Chunk:
    lines = [
        f"Class: {cls.name}",
        f"File: {file_path}",
    ]
    if cls.bases:
        lines.append(f"Inherits from: {', '.join(cls.bases)}")
    if cls.docstring:
        lines.append(f"Docstring: {cls.docstring}")
    lines.append(f"Methods: {', '.join(m.name for m in cls.methods)}")

    return Chunk(
        chunk_id=_build_id(file_path, cls.name),
        content="\n".join(lines),
        chunk_type="class",
        language="python",
        source_file=file_path,
        start_line=cls.lineno,
        metadata={
            "name": cls.name,
            "bases": cls.bases,
            "method_count": len(cls.methods),
            "has_docstring": cls.docstring is not None,
        },
    )


def _format_table_schema(schema: TableSchema, file_path: str) -> Chunk:
    col_lines = [
        f"  - {c['name']} ({c['type']})"
        + (" [PK]" if c["primary_key"] else "")
        + (" [NOT NULL]" if not c["nullable"] else "")
        for c in schema.columns
    ]
    fk_lines = [
        f"  - {fk['column']} -> {fk['references_table']}.{fk['references_column']}"
        for fk in schema.foreign_keys
    ]

    lines = [
        f"SQL Table: {schema.name}",
        f"File: {file_path}",
        "Columns:",
        *col_lines,
    ]
    if fk_lines:
        lines.append("Foreign Keys:")
        lines.extend(fk_lines)

    return Chunk(
        chunk_id=_build_id(file_path, schema.name),
        content="\n".join(lines),
        chunk_type="table_schema",
        language="sql",
        source_file=file_path,
        start_line=schema.lineno,
        metadata={
            "table_name": schema.name,
            "column_count": len(schema.columns),
            "has_foreign_keys": len(schema.foreign_keys) > 0,
            "primary_keys": schema.primary_keys,
        },
    )


def _format_sql_query(query: QueryInfo, file_path: str, index: int) -> Chunk:
    tables_read = [t.name for t in query.tables_read]
    tables_written = [t.name for t in query.tables_written]

    lines = [
        f"SQL Query ({query.query_type})",
        f"File: {file_path}",
    ]
    if tables_read:
        lines.append(f"Tables read: {', '.join(tables_read)}")
    if tables_written:
        lines.append(f"Tables written: {', '.join(tables_written)}")
    if query.joins:
        lines.append(f"Joins: {', '.join(query.joins)}")
    lines.append(f"SQL: {query.raw_sql[:500]}")  # tronqu� si tr�s long

    return Chunk(
        chunk_id=_build_id(file_path, f"query_{index}"),
        content="\n".join(lines),
        chunk_type="sql_query",
        language="sql",
        source_file=file_path,
        start_line=query.lineno,
        metadata={
            "query_type": query.query_type,
            "tables_read": tables_read,
            "tables_written": tables_written,
            "join_count": len(query.joins),
        },
    )


def chunk_parsed_file(parsed: ParsedFile) -> list[Chunk]:
    chunks = []
    file_path = parsed.source_file.relative_path

    # --- Python ---
    if parsed.python_info:
        info = parsed.python_info

        # Chunk module-level (vue d'ensemble du fichier)
        module_lines = [f"Module: {file_path}"]
        if info.docstring:
            module_lines.append(f"Docstring: {info.docstring}")
        if info.imports:
            module_lines.append(f"Imports: {', '.join(info.imports[:10])}")  # top 10
        module_lines.append(
            f"Contains: {len(info.functions)} functions, {len(info.classes)} classes"
        )

        chunks.append(
            Chunk(
                chunk_id=_build_id(file_path, "__module__"),
                content="\n".join(module_lines),
                chunk_type="module",
                language="python",
                source_file=file_path,
                metadata={"has_docstring": info.docstring is not None},
            )
        )

        # Fonctions top-level
        for func in info.functions:
            chunks.append(_format_function(func, file_path))

        # Classes + m�thodes
        for cls in info.classes:
            chunks.append(_format_class(cls, file_path))
            for method in cls.methods:
                chunks.append(_format_function(method, file_path, parent=cls.name))

    # --- SQL ---
    if parsed.sql_info:
        info = parsed.sql_info
        for schema in info.schemas:
            chunks.append(_format_table_schema(schema, file_path))
        for i, query in enumerate(info.queries):
            chunks.append(_format_sql_query(query, file_path, i))

    return chunks



