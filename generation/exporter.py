from pathlib import Path
from generation.assembler import ProjectDoc


def export_to_markdown(project_doc: ProjectDoc, output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    # README.md projet
    readme = out / "README.md"
    readme.write_text(project_doc.project_overview, encoding="utf-8")
    written.append(readme)

    # Un fichier par module
    modules_dir = out / "modules"
    modules_dir.mkdir(exist_ok=True)

    for module in project_doc.modules:
        # Nom de fichier safe depuis le chemin
        safe_name = (
            module.file_path.replace("/", "_")
            .replace("\\", "_")
            .replace(".py", "")
            .replace(".sql", "")
        )
        module_file = modules_dir / f"{safe_name}.md"

        sections = [module.module_doc, "\n---\n"]

        if module.function_docs:
            sections.append("## Functions & Methods\n")
            for name, doc in module.function_docs.items():
                sections.append(doc + "\n\n---\n")

        if module.class_docs:
            sections.append("## Classes\n")
            for name, doc in module.class_docs.items():
                sections.append(doc + "\n\n---\n")

        if module.table_docs:
            sections.append("## SQL Tables\n")
            for name, doc in module.table_docs.items():
                sections.append(doc + "\n\n---\n")

        module_file.write_text("\n".join(sections), encoding="utf-8")
        written.append(module_file)

    # Index global des modules
    index = out / "INDEX.md"
    index_lines = [
        ,
        "# Documentation Index\n\n| Module | Link |\n|--------|------|\n",
    ]
    for module in project_doc.modules:
        safe_name = (
            module.file_path.replace("/", "_")
            .replace("\\", "_")
            .replace(".py", "")
            .replace(".sql", "")
        )
        index_lines.append(
            f"| `{module.file_path}` | [doc](modules/{safe_name}.md) |\n"
        )
    index.write_text("".join(index_lines), encoding="utf-8")
    written.append(index)

    return written
