from pathlib import Path

from src.ingestion.parser_dispatcher import dispatch_parser
from src.ingestion.repo_walker import SourceFile


def test_dispatch_parser_python_route() -> None:
    source_file = SourceFile(
        path=Path("sample.py"),
        language="python",
        content="def f():\n    return 1\n",
        relative_path="sample.py",
    )

    result = dispatch_parser(source_file)

    assert result.python_info is not None
    assert result.sql_info is None
    assert result.ts_result is None
    assert result.python_info.functions[0].name == "f"


def test_dispatch_parser_sql_route() -> None:
    source_file = SourceFile(
        path=Path("query.sql"),
        language="sql",
        content="SELECT 1;",
        relative_path="query.sql",
    )

    result = dispatch_parser(source_file, sql_dialect="postgres")

    assert result.sql_info is not None
    assert result.python_info is None
    assert result.ts_result is None
    assert len(result.sql_info.queries) == 1
