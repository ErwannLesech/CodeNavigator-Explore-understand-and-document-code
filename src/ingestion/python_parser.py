from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    name: str
    docstring: Optional[str]
    args: list[str]
    decorators: list[str]
    lineno: int
    end_lineno: Optional[int] = None  # Line where the function ends
    is_method: bool = False
    source_code: Optional[str] = None  # Full source code of the function


@dataclass
class ClassInfo:
    name: str
    docstring: Optional[str]
    methods: list[FunctionInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class ModuleInfo:
    imports: list[str]
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    docstring: Optional[str]
    module_name: str


def parse_python_file(source: str, module_name: str) -> ModuleInfo:
    tree = ast.parse(source)
    lines = source.split("\n")

    imports: list[str] = []
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []

    def _extract_source(lineno: int, end_lineno: Optional[int]) -> Optional[str]:
        """Extract source code from line numbers (1-indexed)."""
        if not lineno or not end_lineno:
            return None
        try:
            # Convert 1-indexed to 0-indexed
            start_idx = lineno - 1
            end_idx = end_lineno  # end_lineno is inclusive
            if start_idx < 0 or end_idx > len(lines):
                return None
            return "\n".join(lines[start_idx:end_idx])
        except Exception:
            return None

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))
            continue

        if isinstance(node, ast.FunctionDef):
            func_info = FunctionInfo(
                name=node.name,
                docstring=ast.get_docstring(node),
                args=[arg.arg for arg in node.args.args],
                decorators=[ast.unparse(d) for d in node.decorator_list],
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                source_code=_extract_source(node.lineno, node.end_lineno),
            )
            functions.append(func_info)
            continue

        if isinstance(node, ast.ClassDef):
            methods = [
                FunctionInfo(
                    name=member.name,
                    docstring=ast.get_docstring(member),
                    args=[arg.arg for arg in member.args.args],
                    decorators=[ast.unparse(d) for d in member.decorator_list],
                    lineno=member.lineno,
                    end_lineno=member.end_lineno,
                    is_method=True,
                    source_code=_extract_source(member.lineno, member.end_lineno),
                )
                for member in node.body
                if isinstance(member, ast.FunctionDef)
            ]

            class_info = ClassInfo(
                name=node.name,
                docstring=ast.get_docstring(node),
                methods=methods,
                bases=[ast.unparse(base) for base in node.bases],
                lineno=node.lineno,
            )
            classes.append(class_info)

    return ModuleInfo(
        imports=imports,
        functions=functions,
        classes=classes,
        docstring=ast.get_docstring(tree),
        module_name=module_name,
    )
