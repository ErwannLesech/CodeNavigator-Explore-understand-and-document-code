from src.codeNavigator.ingestion.python_parser import parse_python_file


def test_parse_python_file_extracts_module_structure() -> None:
    source = '''
"""Module doc."""
import os
from pathlib import Path


def top(a, b):
    """Top function."""
    return a + b


class User(BaseUser):
    """User class."""

    def method(self, x):
        """Method doc."""
        return x
'''

    result = parse_python_file(source=source, module_name="sample.py")

    assert result.module_name == "sample.py"
    assert result.docstring == "Module doc."
    assert len(result.imports) == 2

    assert len(result.functions) == 1
    assert result.functions[0].name == "top"
    assert result.functions[0].args == ["a", "b"]

    assert len(result.classes) == 1
    cls = result.classes[0]
    assert cls.name == "User"
    assert cls.bases == ["BaseUser"]
    assert len(cls.methods) == 1
    assert cls.methods[0].name == "method"
    assert cls.methods[0].is_method is True

