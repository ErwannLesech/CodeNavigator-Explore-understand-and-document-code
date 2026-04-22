import sys
from unittest.mock import patch

from src import main as main_module


def _parse_with_argv(argv: list[str]):
    with patch.object(sys, "argv", ["prog", *argv]):
        return main_module.parse_args()


def test_parse_args_index_defaults() -> None:
    """Verifie les valeurs par defaut de la commande index."""
    args = _parse_with_argv(["index", "--repo", "sample_repo"])

    assert args.command == "index"
    assert args.repo == "sample_repo"
    assert args.dry_run is False
    assert args.recreate is False
    assert args.dialect == "mysql"


def test_parse_args_index_flags_enabled() -> None:
    """Verifie que les flags booléens de index passent a True."""
    args = _parse_with_argv(
        [
            "index",
            "--repo",
            "sample_repo",
            "--dry-run",
            "--recreate",
            "--dialect",
            "postgres",
        ],
    )

    assert args.command == "index"
    assert args.dry_run is True
    assert args.recreate is True
    assert args.dialect == "postgres"


def test_parse_args_generate_defaults() -> None:
    """Verifie les valeurs par defaut de la commande generate."""
    args = _parse_with_argv(["generate", "--repo", "sample_repo"])

    assert args.command == "generate"
    assert args.repo == "sample_repo"
    assert args.output_docs == "data/output/docs"
    assert args.dialect == "mysql"


def test_parse_args_generate_custom_output() -> None:
    """Verifie que le flag de sortie de generate est pris en compte."""
    args = _parse_with_argv(
        [
            "generate",
            "--repo",
            "sample_repo",
            "--output-docs",
            "custom/docs",
            "--dialect",
            "postgres",
        ],
    )

    assert args.command == "generate"
    assert args.output_docs == "custom/docs"
    assert args.dialect == "postgres"


def test_parse_args_graph_defaults() -> None:
    """Verifie les valeurs par defaut de la commande graph."""
    args = _parse_with_argv(["graph", "--repo", "sample_repo"])

    assert args.command == "graph"
    assert args.repo == "sample_repo"
    assert args.output_graph == "data/output/graph"
    assert args.dialect == "mysql"


def test_parse_args_graph_custom_output() -> None:
    """Verifie que le flag de sortie de graph est pris en compte."""
    args = _parse_with_argv(
        [
            "graph",
            "--repo",
            "sample_repo",
            "--output-graph",
            "custom/graph",
            "--dialect",
            "postgres",
        ],
    )

    assert args.command == "graph"
    assert args.output_graph == "custom/graph"
    assert args.dialect == "postgres"


def test_parse_args_full_defaults() -> None:
    """Verifie les sorties et flags par defaut de la commande full."""
    args = _parse_with_argv(["full", "--repo", "sample_repo"])

    assert args.command == "full"
    assert args.output_docs == "data/output/docs"
    assert args.output_graph == "data/output/graph"
    assert args.recreate is False
    assert args.dry_run is False


def test_parse_args_chat_options() -> None:
    """Verifie le parsing des options de connexion du chatbot."""
    args = _parse_with_argv(
        [
            "chat",
            "--graph",
            "out/graph.json",
            "--qdrant-host",
            "qdrant.internal",
            "--qdrant-port",
            "7000",
            "--qdrant-collection",
            "Chunks",
            "--top-k",
            "9",
        ],
    )

    assert args.command == "chat"
    assert args.graph == "out/graph.json"
    assert args.qdrant_host == "qdrant.internal"
    assert args.qdrant_port == 7000
    assert args.qdrant_collection == "Chunks"
    assert args.top_k == 9
