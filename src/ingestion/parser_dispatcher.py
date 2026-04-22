# ingestion/parser_dispatcher.py
from dataclasses import dataclass
from typing import Optional
from src.ingestion.repo_walker import SourceFile
from src.ingestion.python_parser import parse_python_file, ModuleInfo
from src.ingestion.sql_parser import parse_sql_file, SqlFileInfo
from src.ingestion.treesitter_parser import (
    parse_with_treesitter,
    TreeSitterResult,
)


@dataclass
class ParsedFile:
    source_file: SourceFile
    python_info: Optional[ModuleInfo] = None
    sql_info: Optional[SqlFileInfo] = None
    ts_result: Optional[TreeSitterResult] = None


def dispatch_parser(source_file: SourceFile, sql_dialect: str = "mysql") -> ParsedFile:
    result = ParsedFile(source_file=source_file)
    if source_file.language == "python":
        result.python_info = parse_python_file(
            source_file.content, source_file.relative_path
        )
        return result

    if source_file.language == "sql":
        result.sql_info = parse_sql_file(
            source_file.content, source_file.relative_path, dialect=sql_dialect
        )
        return result

    result.ts_result = parse_with_treesitter(
        source_file.content, source_file.language, source_file.relative_path
    )
    return result
