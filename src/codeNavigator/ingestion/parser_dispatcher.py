# ingestion/parser_dispatcher.py
from dataclasses import dataclass
from typing import Optional
from src.codeNavigator.ingestion.repo_walker import SourceFile
from src.codeNavigator.ingestion.python_parser import parse_python_file, ModuleInfo
from src.codeNavigator.ingestion.sql_parser import parse_sql_file, SqlFileInfo
from src.codeNavigator.ingestion.treesitter_parser import (
    parse_with_treesitter,
    TreeSitterResult,
)


@dataclass
class ParsedFile:
    source_file: SourceFile
    python_info: Optional[ModuleInfo] = None
    sql_info: Optional[SqlFileInfo] = None
    ts_result: Optional[TreeSitterResult] = None

    def summary(self) -> str:
        parts = [f"[{self.source_file.language}] {self.source_file.relative_path}"]
        if self.python_info:
            parts.append(
                f"  {len(self.python_info.functions)} fonctions, {len(self.python_info.classes)} classes"
            )
        if self.sql_info:
            parts.append(
                f"  {len(self.sql_info.schemas)} tables, {len(self.sql_info.queries)} requetes"
            )
        if self.ts_result:
            parts.append(f"  {len(self.ts_result.units)} unites (tree-sitter)")
        return "\n".join(parts)


def dispatch_parser(source_file: SourceFile, sql_dialect: str = "ansi") -> ParsedFile:
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
