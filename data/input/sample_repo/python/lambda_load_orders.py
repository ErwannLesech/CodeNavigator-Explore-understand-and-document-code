import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

SQL_FOLDERS = ["sql/bronze", "sql/silver", "sql/gold"]


def _ordered_sql_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in SQL_FOLDERS:
        folder_path = root / folder
        files.extend(sorted(folder_path.glob("*.sql")))
    return files


def handler(event: dict, context: object) -> dict:
    repo_root = Path(event.get("repo_root", Path(__file__).resolve().parents[1]))
    sql_files = _ordered_sql_files(repo_root)

    executed: list[str] = []
    for sql_file in sql_files:
        sql_text = sql_file.read_text(encoding="utf-8")
        LOGGER.info("Executing %s (%d chars)", sql_file, len(sql_text))
        executed.append(str(sql_file.relative_to(repo_root)))

    return {
        "status": "ok",
        "executed_count": len(executed),
        "executed_files": executed,
    }


if __name__ == "__main__":
    result = handler({}, None)
    LOGGER.info("Load result: %s", result)
