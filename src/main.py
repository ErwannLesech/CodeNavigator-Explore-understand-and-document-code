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


def build_chunks(args):
    return run_indexing(
        args.repo,
        recreate_collection=args.recreate,
        sql_dialect=args.dialect,
        dry_run=args.dry_run,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        qdrant_collection=args.qdrant_collection,
    )


def build_docs(args, chunks):
    generator = DocGenerator()
    return build_project_doc(
        chunks,
        generator,
        detail_level="full",
    )


def build_graph_artifacts(args):
    files = list(walk_repo(args.repo))
    parsed_files = [dispatch_parser(f, sql_dialect=args.dialect) for f in files]

    builder = GraphBuilder()
    builder.ingest(parsed_files)

    nodes = builder.get_nodes()
    edges = builder.get_edges()

    return nodes, edges


def run_chat(args):
    run_chat_cli(
        graph_json_path=args.graph,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        qdrant_collection=args.qdrant_collection,
        top_k=args.top_k,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="CodeNavigator CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Commande index
    idx_cmd = subparsers.add_parser("index", help="Parser et indexer une codebase")
    idx_cmd.add_argument("--repo", required=True)
    idx_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + chunk uniquement (sans embeddings, sans ecriture Qdrant)",
    )
    idx_cmd.add_argument(
        "--recreate",
        action="store_true",
        help="Supprime puis recree la collection Qdrant avant indexation",
    )
    idx_cmd.add_argument("--dialect", default="mysql")
    idx_cmd.add_argument("--qdrant-host", default="localhost")
    idx_cmd.add_argument("--qdrant-port", type=int, default=6333)
    idx_cmd.add_argument("--qdrant-collection", default="CodeNavigatorChunks")

    # Commande generate
    gen_cmd = subparsers.add_parser("generate", help="Generer la documentation")
    gen_cmd.add_argument("--repo", required=True)
    gen_cmd.add_argument("--output-docs", default="data/output/docs")
    gen_cmd.add_argument("--dialect", default="mysql")
    gen_cmd.add_argument("--qdrant-host", default="localhost")
    gen_cmd.add_argument("--qdrant-port", type=int, default=6333)
    gen_cmd.add_argument("--qdrant-collection", default="CodeNavigatorChunks")

    # Commande graph
    graph_cmd = subparsers.add_parser("graph", help="Construire le knowledge graph")
    graph_cmd.add_argument("--repo", required=True)
    graph_cmd.add_argument("--output-graph", default="data/output/graph")
    graph_cmd.add_argument("--dialect", default="mysql")
    graph_cmd.add_argument("--qdrant-host", default="localhost")
    graph_cmd.add_argument("--qdrant-port", type=int, default=6333)
    graph_cmd.add_argument("--qdrant-collection", default="CodeNavigatorChunks")

    # Commande full (index + generate + graph)
    full_cmd = subparsers.add_parser("full", help="Pipeline complet")
    full_cmd.add_argument("--repo", required=True)
    full_cmd.add_argument("--output-docs", default="data/output/docs")
    full_cmd.add_argument("--output-graph", default="data/output/graph")
    full_cmd.add_argument("--recreate", action="store_true")
    full_cmd.add_argument("--dialect", default="mysql")
    full_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + chunk uniquement (sans embeddings, sans ecriture Qdrant)",
    )
    full_cmd.add_argument("--qdrant-host", default="localhost")
    full_cmd.add_argument("--qdrant-port", type=int, default=6333)
    full_cmd.add_argument("--qdrant-collection", default="CodeNavigatorChunks")

    chat_cmd = subparsers.add_parser("chat", help="Lancer le chatbot RAG en CLI")
    chat_cmd.add_argument("--graph", default="data/output/graph/graph.json")
    chat_cmd.add_argument("--qdrant-host", default="localhost")
    chat_cmd.add_argument("--qdrant-port", type=int, default=6333)
    chat_cmd.add_argument("--qdrant-collection", default="CodeNavigatorChunks")
    chat_cmd.add_argument("--top-k", type=int, default=6)

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "index":
        build_chunks(args)

    elif args.command == "generate":
        chunks = build_chunks(args)

        documentation = build_docs(args, chunks)
        export_to_markdown(documentation, args.output_docs)

    elif args.command == "graph":
        nodes, edges = build_graph_artifacts(args)
        export_graph_json(nodes, edges, args.output_graph)

    elif args.command == "full":
        chunks = build_chunks(args)

        documentation = build_docs(args, chunks)
        export_to_markdown(documentation, args.output_docs)

        nodes, edges = build_graph_artifacts(args)
        export_graph_json(nodes, edges, args.output_graph)

    elif args.command == "chat":
        run_chat(args)

    else:
        raise ValueError(
            f"Unknown command: {args.command}, use --help for available commands"
        )


if __name__ == "__main__":
    main()
