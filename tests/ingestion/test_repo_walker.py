from pathlib import Path

from src.ingestion.repo_walker import walk_repo


def test_walk_repo_filters_by_extension_and_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / "ingestion").mkdir()
    (tmp_path / "ingestion" / "a.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "queries.sql").write_text("select 1;\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignored\n", encoding="utf-8")

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("const x = 1;\n", encoding="utf-8")

    files = list(walk_repo(tmp_path))
    rel_paths = {f.relative_path.replace("\\", "/") for f in files}

    assert "ingestion/a.py" in rel_paths
    assert "queries.sql" in rel_paths
    assert "README.md" not in rel_paths
    assert "node_modules/x.js" not in rel_paths

    language_map = {f.relative_path.replace("\\", "/"): f.language for f in files}
    assert language_map["ingestion/a.py"] == "python"
    assert language_map["queries.sql"] == "sql"


def test_walk_repo_strips_utf8_bom_from_python_files(tmp_path: Path) -> None:
    file_path = tmp_path / "bom_file.py"
    file_path.write_bytes("\ufeffimport logging\n".encode("utf-8"))

    files = list(walk_repo(tmp_path))

    assert len(files) == 1
    assert files[0].relative_path == "bom_file.py"
    assert files[0].content.startswith("import logging")
