# rag/cli.py
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from typing import Optional

from src.rag.chatbot import CodeNavigatorChatbot
from src.rag.providers import list_available_models, resolve_default_model


def run_chat_cli(
    graph_json_path: Optional[str] = None,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    qdrant_collection: str = "CodeNavigatorChunks",
    top_k: int = 6,
    model: Optional[str] = None,
):
    print(
        Panel.fit(
            "[bold blue]CodeNavigator[/bold blue] é Chatbot RAG\n"
            "[dim]Interroge ta codebase en langage naturel[/dim]\n"
            "[dim]Commandes : /reset  /sources  /quit[/dim]"
        )
    )

    bot = CodeNavigatorChatbot(
        graph_json_path=graph_json_path,
        top_k=top_k,
        default_model=model,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        qdrant_collection=qdrant_collection,
    )
    show_sources = False

    while True:
        try:
            query = Prompt.ask("\n[bold green]Vous[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[dim]Au revoir.[/dim]")
            break

        if not query:
            continue
        if query == "/quit":
            break
        if query == "/reset":
            bot.reset()
            print("[dim]Historique effacé.[/dim]")
            continue
        if query == "/sources":
            show_sources = not show_sources
            print(
                f"[dim]Affichage des sources : {'activé' if show_sources else 'désactivé'}[/dim]"
            )
            continue

        try:
            response = bot.chat(query)
        except (RuntimeError, ValueError) as exc:
            print(f"[bold red]Erreur:[/bold red] {exc}")
            continue

        print(f"\n[bold blue]CodeNavigator[/bold blue]\n{response.answer}")

        if show_sources and response.sources:
            print("\n[dim]Sources :[/dim]")
            for i, src in enumerate(response.sources, 1):
                print(
                    f"  [dim][{i}] {src.source_file} ({src.chunk_type}) é score: {src.score:.3f}[/dim]"
                )


def run_models_list() -> None:
    models = list_available_models()
    if not models:
        print("[dim]Aucun modèle n'est disponible pour le moment.[/dim]")
        return

    default_model = resolve_default_model(models)
    table = Table(title="Modèles disponibles")
    table.add_column("Type", style="dim", no_wrap=True)
    table.add_column("Provider", style="bold")
    table.add_column("Modèle")
    table.add_column("Label")
    table.add_column("Défaut", justify="center")

    for model in models:
        table.add_row(
            "Cloud" if model.deployment == "cloud" else "Local",
            model.provider,
            model.id,
            model.label,
            "*" if model.id == default_model.id else "",
        )

    print(table)
