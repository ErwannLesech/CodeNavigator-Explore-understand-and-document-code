from dataclasses import dataclass
from collections import defaultdict
from typing import Callable

from src.codeNavigator.embedding.chunker import Chunk
from src.codeNavigator.generation.doc_generator import DocGenerator


@dataclass
class ModuleDoc:
    file_path: str
    module_doc: str
    function_docs: dict[str, str]  # name -> doc
    class_docs: dict[str, str]  # name -> doc
    table_docs: dict[str, str]  # table_name -> doc


@dataclass
class ProjectDoc:
    project_overview: str
    modules: list[ModuleDoc]


def _group_chunks_by_file(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.source_file].append(chunk)
    return dict(grouped)


def _get_imports_from_chunks(chunks: list[Chunk]) -> list[str]:
    for chunk in chunks:
        if chunk.chunk_type == "module" and chunk.metadata.get("imports"):
            return chunk.metadata["imports"]
    return []


def _component_summaries_for_compact(chunks: list[Chunk], limit: int = 20) -> list[str]:
    summaries: list[str] = []
    for chunk in chunks:
        name = chunk.metadata.get("name") or chunk.metadata.get("table_name") or chunk.chunk_id
        summaries.append(f"- {chunk.chunk_type}: {name}")
        if len(summaries) >= limit:
            break
    return summaries


def estimate_doc_workload(chunks: list[Chunk], detail_level: str = "compact") -> tuple[int, int]:
    grouped = _group_chunks_by_file(chunks)
    module_count = len(grouped)
    compact_mode = detail_level.lower() != "full"

    if compact_mode:
        # 1 appel LLM par module + 1 appel pour la vue projet
        return module_count + 1, module_count

    functions = sum(1 for c in chunks if c.chunk_type == "function")
    methods = sum(1 for c in chunks if c.chunk_type == "method")
    classes = sum(1 for c in chunks if c.chunk_type == "class")
    tables = sum(1 for c in chunks if c.chunk_type == "table_schema")

    # Mode full: fonctions + methodes + classes + tables + modules + projet
    total = functions + methods + classes + tables + module_count + 1
    return total, module_count


def build_project_doc(
    chunks: list[Chunk],
    generator: DocGenerator,
    detail_level: str = "compact",
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> ProjectDoc:
    grouped = _group_chunks_by_file(chunks)
    module_docs = []
    compact_mode = detail_level.lower() != "full"
    total_steps, _ = estimate_doc_workload(chunks, detail_level)
    completed_steps = 0

    def _notify_progress(label: str) -> None:
        nonlocal completed_steps
        completed_steps += 1
        if progress_callback is not None:
            progress_callback(completed_steps, total_steps, label)

    for file_path, file_chunks in grouped.items():
        # Trier les chunks par type pour respecter l'ordre de g�n�ration
        functions = [c for c in file_chunks if c.chunk_type == "function"]
        methods = [c for c in file_chunks if c.chunk_type == "method"]
        classes = [c for c in file_chunks if c.chunk_type == "class"]
        tables = [c for c in file_chunks if c.chunk_type == "table_schema"]
        # sql_query : pas de doc LLM individuelle, utilis� uniquement au niveau module

        function_docs = {}
        class_docs = {}
        table_docs = {}

        if not compact_mode:
            # 1. Fonctions top-level
            for chunk in functions:
                name = chunk.metadata.get("name", chunk.chunk_id)
                function_docs[name] = generator.document_function(chunk)
                _notify_progress(f"function:{name}")

        # 2. M�thodes group�es par classe
        methods_by_class: dict[str, list[Chunk]] = defaultdict(list)
        for chunk in methods:
            parent = chunk.metadata.get("parent_class", "__unknown__")
            methods_by_class[parent].append(chunk)

        if not compact_mode:
            # 3. Classes � inject�es avec les docs de leurs m�thodes
            for chunk in classes:
                class_name = chunk.metadata.get("name", chunk.chunk_id)
                related_method_docs = [
                    function_docs.get(m.metadata.get("name", ""), "")
                    for m in methods_by_class.get(class_name, [])
                ]
                class_docs[class_name] = generator.document_class(
                    chunk, related_method_docs
                )
                _notify_progress(f"class:{class_name}")

                # Documenter les m�thodes individuellement aussi
                for method_chunk in methods_by_class.get(class_name, []):
                    method_name = method_chunk.metadata.get("name", method_chunk.chunk_id)
                    function_docs[f"{class_name}.{method_name}"] = (
                        generator.document_function(method_chunk)
                    )
                    _notify_progress(f"method:{class_name}.{method_name}")

            # 4. Tables SQL
            for chunk in tables:
                table_name = chunk.metadata.get("table_name", chunk.chunk_id)
                table_docs[table_name] = generator.document_table(chunk)
                _notify_progress(f"table:{table_name}")

        # 5. Module-level
        imports = _get_imports_from_chunks(file_chunks)
        module_component_summaries: list[str]
        if compact_mode:
            module_component_summaries = _component_summaries_for_compact(
                [*functions, *classes, *tables],
                limit=20,
            )
        else:
            module_component_summaries = list(function_docs.values())

        module_doc = generator.document_module(
            file_path=file_path,
            function_docs=module_component_summaries,
            class_docs=[] if compact_mode else list(class_docs.values()),
            imports=imports,
        )
        _notify_progress(f"module:{file_path}")

        module_docs.append(
            ModuleDoc(
                file_path=file_path,
                module_doc=module_doc,
                function_docs=function_docs,
                class_docs=class_docs,
                table_docs=table_docs,
            )
        )

    # 6. Vue projet globale
    modules_summary = [
        {
            "file": m.file_path,
            # On injecte uniquement le r�sum� du module, pas toute la doc
            "summary": m.module_doc[:300],
        }
        for m in module_docs
    ]
    project_overview = generator.document_project(modules_summary)
    _notify_progress("project_overview")

    return ProjectDoc(project_overview=project_overview, modules=module_docs)



