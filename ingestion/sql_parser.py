# ingestion/sql_parser.py
import sqlglot
import sqlglot.expressions as exp
from dataclasses import dataclass
from typing import Optional


@dataclass
class TableRef:
    name: str
    alias: Optional[str]
    schema: Optional[str]


@dataclass
class ColumnRef:
    name: str
    table: Optional[str]


@dataclass
class QueryInfo:
    query_type: str  # SELECT, INSERT, UPDATE, CREATE, etc.
    tables_read: list[TableRef]
    tables_written: list[TableRef]
    columns_referenced: list[ColumnRef]
    joins: list[str]
    raw_sql: str
    lineno: Optional[int] = None


@dataclass
class TableSchema:
    name: str
    columns: list[
        dict
    ]  # {"name": str, "type": str, "nullable": bool, "primary_key": bool}
    primary_keys: list[str]
    foreign_keys: list[
        dict
    ]  # {"column": str, "references_table": str, "references_column": str}
    lineno: Optional[int] = None


@dataclass
class SqlFileInfo:
    schemas: list[TableSchema]
    queries: list[QueryInfo]
    source_file: str


def _extract_table_ref(table_expr) -> TableRef:
    return TableRef(
        name=table_expr.name,
        alias=table_expr.alias or None,
        schema=table_expr.db or None,
    )


def _parse_create_table(stmt) -> Optional[TableSchema]:
    """Extrait le schema d'un CREATE TABLE."""
    table_name = stmt.find(exp.Table)
    if not table_name:
        return None

    columns = []
    primary_keys = []
    foreign_keys = []

    for col_def in stmt.find_all(exp.ColumnDef):
        col_name = col_def.name
        col_type = col_def.args.get("kind")
        col_type_str = col_type.sql() if col_type else "UNKNOWN"

        is_pk = any(
            isinstance(c, exp.PrimaryKeyColumnConstraint)
            for c in col_def.find_all(exp.ColumnConstraint)
        )
        not_null = any(
            isinstance(c, exp.NotNullColumnConstraint)
            for c in col_def.find_all(exp.ColumnConstraint)
        )
        if is_pk:
            primary_keys.append(col_name)

        columns.append(
            {
                "name": col_name,
                "type": col_type_str,
                "nullable": not not_null and not is_pk,
                "primary_key": is_pk,
            }
        )

    # Clés étrangères déclarées en contrainte de table
    for fk in stmt.find_all(exp.ForeignKey):
        fk_cols = [c.name for c in fk.find_all(exp.Column)]
        ref = fk.find(exp.Reference)
        if ref:
            ref_table = ref.find(exp.Table)
            ref_cols = [c.name for c in ref.find_all(exp.Column)]
            for fc, rc in zip(fk_cols, ref_cols):
                foreign_keys.append(
                    {
                        "column": fc,
                        "references_table": ref_table.name if ref_table else "unknown",
                        "references_column": rc,
                    }
                )

    return TableSchema(
        name=table_name.name,
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys,
    )


def _parse_query(stmt) -> QueryInfo:
    """Extrait le lineage d'une requête DML (SELECT, INSERT, UPDATE, DELETE)."""
    query_type = type(stmt).__name__.upper()

    tables_read = []
    tables_written = []
    joins = []

    def _add_unique(target: list[TableRef], refs: list[TableRef]) -> None:
        existing = {(t.schema, t.name, t.alias) for t in target}
        for ref in refs:
            key = (ref.schema, ref.name, ref.alias)
            if key not in existing:
                target.append(ref)
                existing.add(key)

    def _table_expr_ref(table_expr: object | None) -> list[TableRef]:
        if isinstance(table_expr, exp.Table):
            return [_extract_table_ref(table_expr)]
        if isinstance(table_expr, exp.Schema) and isinstance(table_expr.this, exp.Table):
            return [_extract_table_ref(table_expr.this)]
        return []

    if isinstance(stmt, exp.Select):
        _add_unique(tables_read, [_extract_table_ref(t) for t in stmt.find_all(exp.Table)])

    elif isinstance(stmt, exp.Insert):
        _add_unique(tables_written, _table_expr_ref(stmt.this))
        expression = stmt.args.get("expression")
        if expression is not None:
            _add_unique(
                tables_read,
                [_extract_table_ref(t) for t in expression.find_all(exp.Table)],
            )

    elif isinstance(stmt, exp.Update):
        written = _table_expr_ref(stmt.this)
        _add_unique(tables_written, written)
        written_names = {t.name for t in written}
        _add_unique(
            tables_read,
            [
                _extract_table_ref(t)
                for t in stmt.find_all(exp.Table)
                if t.name not in written_names
            ],
        )

    elif isinstance(stmt, exp.Delete):
        written = _table_expr_ref(stmt.this)
        _add_unique(tables_written, written)
        written_names = {t.name for t in written}
        _add_unique(
            tables_read,
            [
                _extract_table_ref(t)
                for t in stmt.find_all(exp.Table)
                if t.name not in written_names
            ],
        )

    elif isinstance(stmt, exp.Merge):
        written = _table_expr_ref(stmt.this)
        _add_unique(tables_written, written)
        written_names = {t.name for t in written}
        _add_unique(
            tables_read,
            [
                _extract_table_ref(t)
                for t in stmt.find_all(exp.Table)
                if t.name not in written_names
            ],
        )

    elif isinstance(stmt, exp.Create) and stmt.find(exp.Table):
        # CREATE TABLE ... AS SELECT ...
        _add_unique(tables_written, _table_expr_ref(stmt.this))
        expression = stmt.args.get("expression")
        if expression is not None:
            _add_unique(
                tables_read,
                [_extract_table_ref(t) for t in expression.find_all(exp.Table)],
            )

    else:
        _add_unique(tables_read, [_extract_table_ref(t) for t in stmt.find_all(exp.Table)])

    # JOINs explicites
    for join in stmt.find_all(exp.Join):
        join_table = join.find(exp.Table)
        if join_table:
            joins.append(f"{join.args.get('kind', '')} JOIN {join_table.name}".strip())

    # Colonnes référencées
    columns = [
        ColumnRef(name=col.name, table=col.table or None)
        for col in stmt.find_all(exp.Column)
    ]

    return QueryInfo(
        query_type=query_type,
        tables_read=tables_read,
        tables_written=tables_written,
        columns_referenced=columns,
        joins=joins,
        raw_sql=stmt.sql(),
    )


def parse_sql_file(source: str, file_path: str, dialect: str = "ansi") -> SqlFileInfo:
    """
    Parse un fichier SQL complet.
    dialect: "ansi", "mysql", "postgres", "bigquery", "snowflake", etc.
    """
    schemas = []
    queries = []

    try:
        statements = sqlglot.parse(
            source, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN
        )
    except Exception:
        # En cas d'erreur fatale, on retourne un résultat vide plutôt que de crasher
        return SqlFileInfo(schemas=[], queries=[], source_file=file_path)

    for stmt in statements:
        if stmt is None:
            continue
        if isinstance(stmt, exp.Create) and stmt.find(exp.Table):
            schema = _parse_create_table(stmt)
            if schema:
                schemas.append(schema)
        if isinstance(
            stmt, (exp.Select, exp.Insert, exp.Update, exp.Delete, exp.Merge)
        ) or (
            isinstance(stmt, exp.Create) and stmt.find(exp.Table) and stmt.args.get("expression") is not None
        ):
            queries.append(_parse_query(stmt))

    return SqlFileInfo(schemas=schemas, queries=queries, source_file=file_path)
