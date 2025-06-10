import os
import sys
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

# Add the parent directory to sys.path to allow importing modules from Config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import ws_config_handler as WebSocketConfig

# Initialize the Rich console for pretty terminal output
console = Console()

def edit_ws_uris_menu(console):
    """
    Interactive menu to edit WebSocket server URIs and tokens.
    Allows adding, editing, removing, and saving configurations.
    """
    # Load current URIs and tokens from configuration
    uris, tokens, _ = WebSocketConfig.get_ws_config()

    while True:
        console.clear()
        console.rule("[bold blue]Edit WebSocket Server URIs")

        # Create a table to display current URIs and tokens
        table = Table(title="Current WebSocket URIs", show_lines=True)
        table.add_column("Index", style="cyan", justify="center")
        table.add_column("URI", style="magenta")
        table.add_column("Token", style="yellow")

        # Populate the table with current URIs and tokens (show only first 6 chars of token)
        for idx, (uri, token) in enumerate(zip(uris, tokens), 1):
            token_display = token[:6] + "..." if token else ""
            table.add_row(str(idx), uri, token_display)

        console.print(table)
        console.print(
            "[bold green]Options:[/bold green] [yellow]add[/yellow], [yellow]edit[/yellow], [yellow]remove[/yellow], [yellow]save[/yellow], [yellow]cancel[/yellow]")

        # Prompt user for action
        action = Prompt.ask("[bold yellow]Choose an action", choices=[
                            "add", "edit", "remove", "save", "cancel"])

        if action == "add":
            # Add a new URI and token
            new_uri = Prompt.ask("[bold cyan]Enter new WebSocket URI")
            new_token = Prompt.ask("[bold cyan]Enter token for this URI")
            if new_uri:
                uris.append(new_uri.strip())
                tokens.append(new_token.strip())

        elif action == "edit":
            # Edit an existing URI and/or token
            if not uris:
                console.print("[red]No URIs to edit.[/red]")
                continue
            idx = Prompt.ask("[bold cyan]Enter index to edit", choices=[
                             str(i) for i in range(1, len(uris)+1)])
            idx = int(idx) - 1
            new_uri = Prompt.ask(
                f"[bold cyan]Edit URI [{uris[idx]}]", default=uris[idx])
            new_token = Prompt.ask(
                f"[bold cyan]Edit token [{tokens[idx][:6]+'...' if tokens[idx] else ''}]", default=tokens[idx])
            uris[idx] = new_uri.strip()
            tokens[idx] = new_token.strip()

        elif action == "remove":
            # Remove a URI and its token
            if not uris:
                console.print("[red]No URIs to remove.[/red]")
                continue
            idx = Prompt.ask("[bold cyan]Enter index to remove", choices=[
                             str(i) for i in range(1, len(uris)+1)])
            idx = int(idx) - 1
            removed_uri = uris.pop(idx)
            removed_token = tokens.pop(idx)
            console.print(f"[green]Removed: {removed_uri}[/green]")

        elif action == "save":
            # Save the current URIs and tokens to the configuration file
            WebSocketConfig.save_ws_config(uris=uris, tokens=tokens)
            console.print("[green]URIs and tokens saved to .env[/green]")
            Prompt.ask("[bold cyan]Press ENTER to return to the menu...")
            break

        elif action == "cancel":
            # Exit without saving changes
            console.print("[yellow]No changes saved.[/yellow]")
            Prompt.ask("[bold cyan]Press ENTER to return to the menu...")
            break
