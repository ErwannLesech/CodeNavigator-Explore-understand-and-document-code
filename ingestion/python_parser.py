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
    is_method: bool = False


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

    imports: list[str] = []
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))
            continue

        if isinstance(node, ast.FunctionDef):
            functions.append(
                FunctionInfo(
                    name=node.name,
                    docstring=ast.get_docstring(node),
                    args=[arg.arg for arg in node.args.args],
                    decorators=[ast.unparse(d) for d in node.decorator_list],
                    lineno=node.lineno,
                )
            )
            continue

        if isinstance(node, ast.ClassDef):
            methods = [
                FunctionInfo(
                    name=member.name,
                    docstring=ast.get_docstring(member),
                    args=[arg.arg for arg in member.args.args],
                    decorators=[ast.unparse(d) for d in member.decorator_list],
                    lineno=member.lineno,
                    is_method=True,
                )
                for member in node.body
                if isinstance(member, ast.FunctionDef)
            ]

            classes.append(
                ClassInfo(
                    name=node.name,
                    docstring=ast.get_docstring(node),
                    methods=methods,
                    bases=[ast.unparse(base) for base in node.bases],
                    lineno=node.lineno,
                )
            )

    return ModuleInfo(
        imports=imports,
        functions=functions,
        classes=classes,
        docstring=ast.get_docstring(tree),
        module_name=module_name,
    )
