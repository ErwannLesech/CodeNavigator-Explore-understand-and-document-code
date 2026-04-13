# rag/cli.py
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from typing import Optional
from src.codeNavigator.rag.chatbot import CodeNavigatorChatbot


def run_chat_cli(graph_json_path: Optional[str] = None):
    print(
        Panel.fit(
            "[bold blue]CodeNavigator[/bold blue] � Chatbot RAG\n"
            "[dim]Interroge ta codebase en langage naturel[/dim]\n"
            "[dim]Commandes : /reset  /sources  /quit[/dim]"
        )
    )

    bot = CodeNavigatorChatbot(graph_json_path=graph_json_path)
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
            print("[dim]Historique effac�.[/dim]")
            continue
        if query == "/sources":
            show_sources = not show_sources
            print(
                f"[dim]Affichage des sources : {'activ�' if show_sources else 'd�sactiv�'}[/dim]"
            )
            continue

        response = bot.chat(query)

        print(f"\n[bold blue]CodeNavigator[/bold blue]\n{response.answer}")

        if show_sources and response.sources:
            print("\n[dim]Sources :[/dim]")
            for i, src in enumerate(response.sources, 1):
                print(
                    f"  [dim][{i}] {src.source_file} ({src.chunk_type}) � score: {src.score:.3f}[/dim]"
                )
