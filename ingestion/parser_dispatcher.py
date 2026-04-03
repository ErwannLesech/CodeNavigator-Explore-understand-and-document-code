# ingestion/parser_dispatcher.py
from dataclasses import dataclass
from typing import Optional
import logging
from ingestion.repo_walker import SourceFile
from ingestion.python_parser import parse_python_file, ModuleInfo
from ingestion.sql_parser import parse_sql_file, SqlFileInfo
from ingestion.treesitter_parser import parse_with_treesitter, TreeSitterResult

logger = logging.getLogger(__name__)


@dataclass
class ParsedFile:
    source_file: SourceFile
    python_info: Optional[ModuleInfo] = None
    sql_info: Optional[SqlFileInfo] = None
    ts_result: Optional[TreeSitterResult] = None

    def summary(self) -> str:
        parts = [f"[{self.source_file.language}] {self.source_file.relative_path}"]
        if self.python_info:
            parts.append(f"  {len(self.python_info.functions)} fonctions, {len(self.python_info.classes)} classes")
        if self.sql_info:
            parts.append(f"  {len(self.sql_info.schemas)} tables, {len(self.sql_info.queries)} requetes")
        if self.ts_result:
            parts.append(f"  {len(self.ts_result.units)} unites (tree-sitter)")
        return "\n".join(parts)


def dispatch_parser(source_file: SourceFile, sql_dialect: str = "ansi") -> ParsedFile:
    result = ParsedFile(source_file=source_file)
    logger.debug(f"dispatch_parser: language={source_file.language}, file={source_file.relative_path}")

    try:
        if source_file.language == "python":
            logger.debug(f"  Using python_parser for {source_file.relative_path}")
            result.python_info = parse_python_file(source_file.content, source_file.relative_path)
            logger.debug(f"  Python parse complete: {result.summary()}")

        elif source_file.language == "sql":
            logger.debug(f"  Using sql_parser for {source_file.relative_path}")
            result.sql_info = parse_sql_file(source_file.content, source_file.relative_path, dialect=sql_dialect)
            logger.debug(f"  SQL parse complete: {result.summary()}")

        else:
            logger.debug(f"  Using treesitter_parser for {source_file.relative_path} (language={source_file.language})")
            result.ts_result = parse_with_treesitter(source_file.content, source_file.language, source_file.relative_path)
            logger.debug(f"  TreeSitter parse complete: {result.summary()}")

        return result
    
    except Exception as e:
        logger.error(f"Error in dispatch_parser for {source_file.relative_path}: {e}", exc_info=True)
        raise