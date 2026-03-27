from pathlib import Path

from ingestion.python_parser import parse_python_file
from ingestion.repo_walker import walk_repo
from rich import print


def main() -> None:
    repo_path = Path("./data/input/sample_repo")

    for source_file in walk_repo(repo_path):
        print(f"[blue]{source_file.relative_path}[/blue] ({source_file.language})")

        if source_file.language == "python":
            info = parse_python_file(source_file.content, source_file.relative_path)
            print(f"  Imports: {len(info.imports)}")
            print(f"  Fonctions: {[f.name for f in info.functions]}")
            print(f"  Classes: {[c.name for c in info.classes]}")


if __name__ == "__main__":
    main()
