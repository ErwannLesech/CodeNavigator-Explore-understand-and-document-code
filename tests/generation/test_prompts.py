from src.embedding.chunker import Chunk
from src.generation.doc_generator import DocGenerator
from src.generation.prompts import (
    prompt_for_class,
    prompt_for_function,
    prompt_for_module,
    prompt_rag,
)


def test_prompt_for_function_includes_function_name_and_source() -> None:
    chunk = Chunk(
        chunk_id="sample.py::top",
        content="def top(a, b):\n    return a + b",
        chunk_type="function",
        language="python",
        source_file="sample.py",
        metadata={"name": "top"},
    )

    prompt = prompt_for_function(chunk)

    assert "top()" in prompt
    assert "def top(a, b):" in prompt
    assert "## Format de sortie (strict)" in prompt


def test_prompt_for_class_includes_bases_and_method_docs() -> None:
    chunk = Chunk(
        chunk_id="sample.py::User",
        content="class User(BaseUser):\n    pass",
        chunk_type="class",
        language="python",
        source_file="sample.py",
        metadata={"name": "User", "bases": ["BaseUser"]},
    )

    prompt = prompt_for_class(chunk, method_docs=["### method\nDoc method"])

    assert "Class `User`" in prompt
    assert "BaseUser" in prompt
    assert "Methodes deja documentees" in prompt
    assert "Doc method" in prompt


def test_prompt_for_module_and_rag_include_optional_sections() -> None:
    module_prompt = prompt_for_module(
        file_path="sample.py",
        function_docs=["Function doc"],
        class_docs=["Class doc"],
        imports=["os", "pathlib"],
    )

    rag_prompt = prompt_rag(
        query="What does the module do?",
        context="[Source 1] sample context",
        graph_context="module -> class",
    )

    assert "## Module: sample.py" in module_prompt
    assert "os" in module_prompt
    assert "Function doc" in module_prompt
    assert "Class doc" in module_prompt

    assert "## Contexte de dependances (graphe de connaissances)" in rag_prompt
    assert "module -> class" in rag_prompt
    assert "What does the module do?" in rag_prompt


def test_sanitize_markdown_response_strips_code_fences() -> None:
    content = "\n```markdown\n# Title\n```\n"

    sanitized = DocGenerator._sanitize_markdown_response(content)

    assert sanitized == "# Title"
