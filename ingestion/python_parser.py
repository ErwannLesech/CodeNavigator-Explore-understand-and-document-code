from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


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
    try:
        logger.debug(f"Parsing Python file: {module_name}")
        tree = ast.parse(source)
        logger.debug(f"AST parsed successfully for {module_name}")

        imports: list[str] = []
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []

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
                )
                functions.append(func_info)
                logger.debug(f"  Found function: {node.name}")
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

                class_info = ClassInfo(
                    name=node.name,
                    docstring=ast.get_docstring(node),
                    methods=methods,
                    bases=[ast.unparse(base) for base in node.bases],
                    lineno=node.lineno,
                )
                classes.append(class_info)
                logger.debug(f"  Found class: {node.name} with {len(methods)} methods")

        result = ModuleInfo(
            imports=imports,
            functions=functions,
            classes=classes,
            docstring=ast.get_docstring(tree),
            module_name=module_name,
        )
        logger.debug(f"Python parse complete for {module_name}: {len(functions)} functions, {len(classes)} classes")
        return result
    
    except Exception as e:
        logger.error(f"Error parsing Python file {module_name}: {e}", exc_info=True)
        raise
