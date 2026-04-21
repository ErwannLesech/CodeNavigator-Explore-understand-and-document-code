import argparse
from src.embedding.indexer import run_indexing
from src.generation.assembler import build_project_doc
from src.generation.doc_generator import DocGenerator
from src.generation.exporter import export_to_markdown

from src.ingestion.repo_walker import walk_repo
from src.ingestion.parser_dispatcher import dispatch_parser
from src.graph.builder import GraphBuilder
from src.graph.json_exporter import export_graph_json

from src.rag.cli import run_chat_cli


def main():
    parser = argparse.ArgumentParser(description="CodeNavigator CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Commande index
    idx = subparsers.add_parser("index", help="Parser et indexer une codebase")
    idx.add_argument("--repo", required=True)
    idx.add_argument("--dry-run", action="store_true")
    idx.add_argument("--recreate", action="store_true")
    idx.add_argument("--dialect", default="mysql")

    # Commande generate
    gen = subparsers.add_parser("generate", help="Generer la documentation")
    gen.add_argument("--repo", required=True)
    gen.add_argument("--output", default="data/output/docs")
    gen.add_argument("--dialect", default="mysql")

    graph_cmd = subparsers.add_parser("graph", help="Construire le knowledge graph")
    graph_cmd.add_argument("--repo", required=True)
    graph_cmd.add_argument("--output", default="data/output/graph")
    graph_cmd.add_argument("--dialect", default="mysql")

    # Commande full (index + generate)
    full = subparsers.add_parser("full", help="Pipeline complet")
    full.add_argument("--repo", required=True)
    full.add_argument("--output", default="data/output/docs")
    full.add_argument("--recreate", action="store_true")
    full.add_argument("--dialect", default="mysql")

    chat_cmd = subparsers.add_parser("chat", help="Lancer le chatbot RAG en CLI")
    chat_cmd.add_argument("--graph", default="data/output/graph/graph.json")

    args = parser.parse_args()

    if args.command == "index":
        run_indexing(
            args.repo,
            recreate_collection=args.recreate,
            sql_dialect=args.dialect,
            dry_run=args.dry_run,
        )

    elif args.command == "generate":
        chunks = run_indexing(args.repo, sql_dialect=args.dialect, dry_run=True)
        generator = DocGenerator()
        project_doc = build_project_doc(
            chunks,
            generator,
            detail_level="full",
        )
        export_to_markdown(project_doc, args.output)

    elif args.command == "graph":
        files = list(walk_repo(args.repo))
        parsed_files = [dispatch_parser(f, sql_dialect=args.dialect) for f in files]

        builder = GraphBuilder()
        builder.ingest(parsed_files)

        nodes = builder.get_nodes()
        edges = builder.get_edges()

        export_graph_json(nodes, edges, output_path=f"{args.output}/graph.json")

    elif args.command == "full":
        chunks = run_indexing(
            args.repo, recreate_collection=args.recreate, sql_dialect=args.dialect
        )
        generator = DocGenerator()
        project_doc = build_project_doc(
            chunks,
            generator,
            detail_level="full",
        )
        export_to_markdown(project_doc, args.output)

    elif args.command == "chat":
        run_chat_cli(graph_json_path=args.graph)


if __name__ == "__main__":
    main()
