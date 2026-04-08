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
    query_type: str          # SELECT, INSERT, UPDATE, CREATE, etc.
    tables_read: list[TableRef]
    tables_written: list[TableRef]
    columns_referenced: list[ColumnRef]
    joins: list[str]
    raw_sql: str
    lineno: Optional[int] = None


@dataclass
class TableSchema:
    name: str
    columns: list[dict]      # {"name": str, "type": str, "nullable": bool, "primary_key": bool}
    primary_keys: list[str]
    foreign_keys: list[dict] # {"column": str, "references_table": str, "references_column": str}
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
        schema=table_expr.db or None
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

        columns.append({
            "name": col_name,
            "type": col_type_str,
            "nullable": not not_null and not is_pk,
            "primary_key": is_pk
        })

    # Clés étrangères déclarées en contrainte de table
    for fk in stmt.find_all(exp.ForeignKey):
        fk_cols = [c.name for c in fk.find_all(exp.Column)]
        ref = fk.find(exp.Reference)
        if ref:
            ref_table = ref.find(exp.Table)
            ref_cols = [c.name for c in ref.find_all(exp.Column)]
            for fc, rc in zip(fk_cols, ref_cols):
                foreign_keys.append({
                    "column": fc,
                    "references_table": ref_table.name if ref_table else "unknown",
                    "references_column": rc
                })

    return TableSchema(
        name=table_name.name,
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys
    )


def _parse_query(stmt) -> QueryInfo:
    """Extrait le lineage d'une requête DML (SELECT, INSERT, UPDATE, DELETE)."""
    query_type = type(stmt).__name__.upper()

    tables_read = []
    tables_written = []
    joins = []

    # Tables lues (FROM + JOINs)
    for table in stmt.find_all(exp.Table):
        parent = table.parent
        if isinstance(parent, (exp.Insert, exp.Update, exp.Delete)):
            tables_written.append(_extract_table_ref(table))
        else:
            tables_read.append(_extract_table_ref(table))

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
        raw_sql=stmt.sql()
    )


def parse_sql_file(source: str, file_path: str, dialect: str = "ansi") -> SqlFileInfo:
    """
    Parse un fichier SQL complet.
    dialect: "ansi", "mysql", "postgres", "bigquery", "snowflake", etc.
    """
    schemas = []
    queries = []

    try:
        statements = sqlglot.parse(source, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
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
        elif isinstance(stmt, (exp.Select, exp.Insert, exp.Update, exp.Delete, exp.Merge)):
            queries.append(_parse_query(stmt))

    return SqlFileInfo(schemas=schemas, queries=queries, source_file=file_path)