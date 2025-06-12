import os
import sys
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.layout import Layout

# Add the parent directory to sys.path to allow importing modules from Config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import ws_config_handler as WebSocketConfig

# Add platform-specific imports for key handling
if os.name == 'nt':  # Windows
    import msvcrt
else:  # Unix/Linux/macOS
    import termios
    import tty

# Initialize the Rich console for pretty terminal output
console = Console()

def clear_console():
    """
    Clear the console screen.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def get_key():
    """
    Get a single key press from the user in a cross-platform way.
    """
    if os.name == 'nt':  # Windows
        key = msvcrt.getch()
        if key == b'\xe0':  # Special key prefix on Windows
            key = msvcrt.getch()
            if key == b'H':  # Up arrow
                return 'up'
            elif key == b'P':  # Down arrow
                return 'down'
        elif key == b'\r':  # Enter key
            return 'enter'
        elif key == b'\x1b':  # Escape key
            return 'esc'
    else:  # Unix/Linux/macOS
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)
            if key == '\x1b':  # Escape sequence
                key += sys.stdin.read(2)
                if key == '\x1b[A':  # Up arrow
                    return 'up'
                elif key == '\x1b[B':  # Down arrow
                    return 'down'
                elif len(key) == 1:  # Just escape
                    return 'esc'
            elif key == '\r' or key == '\n':  # Enter key
                return 'enter'
            elif key == '\x1b':  # Escape key
                return 'esc'
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    return None

def get_terminal_size():
    """
    Get the current terminal size.
    """
    return console.size

def create_uri_header():
    """
    Create the header panel for URI menu.
    """
    header_text = Text("Edit WebSocket Server URIs", style="bold blue", justify="center")
    return Panel(
        Align.center(header_text),
        style="bold blue",
        padding=(0, 2),
        height=3
    )

def create_uri_footer():
    """
    Create the footer panel with controls for URI menu.
    """
    help_text = Text.assemble(
        ("Navigation: ", "bold cyan"),
        ("↑↓ ", "bold yellow"), ("Move  ", "white"),
        ("Enter ", "bold yellow"), ("Select  ", "white"),
        ("Esc ", "bold yellow"), ("Cancel", "white")
    )
    return Panel(
        Align.center(help_text),
        title="[bold cyan]Controls[/bold cyan]",
        style="cyan",
        padding=(0, 2),
        height=3
    )

def create_uri_table_content(uris, tokens, terminal_width, terminal_height):
    """
    Create the URI table that fits in the available space.
    """
    # Create table with optimized column widths
    table = Table(title="Current WebSocket URIs", show_lines=True, expand=False)
    
    # Calculate optimal column widths based on terminal size
    available_width = terminal_width - 10  # Account for padding and borders
    index_width = 6
    token_width = 10
    uri_width = max(20, available_width - index_width - token_width - 6)  # 6 for separators
    
    table.add_column("Index", style="cyan", justify="center", width=index_width)
    table.add_column("URI", style="magenta", width=uri_width)
    table.add_column("Token", style="yellow", width=token_width)

    if uris:
        # Limit the number of rows shown to prevent overflow
        max_rows = max(3, (terminal_height - 12) // 3)  # Reserve space for header, footer, and menu
        visible_uris = uris[:max_rows]
        visible_tokens = tokens[:max_rows]
        
        for idx, (uri, token) in enumerate(zip(visible_uris, visible_tokens), 1):
            token_display = token[:8] + "..." if len(token) > 8 else token
            # Truncate URI to fit column width
            if len(uri) > uri_width - 3:
                uri_display = uri[:uri_width-6] + "..."
            else:
                uri_display = uri
            table.add_row(str(idx), uri_display, token_display)
        
        # Show indicator if there are more URIs
        if len(uris) > max_rows:
            table.add_row("...", f"[dim]+{len(uris) - max_rows} more[/dim]", "[dim]...[/dim]")
    else:
        table.add_row("--", "[dim]No URIs configured[/dim]", "[dim]--[/dim]")
    
    return table

def create_uri_menu_content(menu_options, selected_index, uris_available):
    """
    Create the menu content that fits in the available space.
    """
    content = []
    content.append("[bold cyan]Menu Options:[/bold cyan]")
    content.append("")  # Empty line for spacing
    
    for i, (option_text, action) in enumerate(menu_options):
        prefix = "► " if i == selected_index else "  "
        
        # Check if option should be disabled
        disabled = action in ["edit", "remove"] and not uris_available
        
        if disabled:
            if i == selected_index:
                content.append(f"[bold yellow]{prefix}[/bold yellow][bold red]{option_text}[/bold red] [dim red](No URIs)[/dim red]")
            else:
                content.append(f"[red]{prefix}{option_text}[/red] [dim red](No URIs)[/dim red]")
        else:
            if i == selected_index:
                content.append(f"[bold yellow]{prefix}[/bold yellow][bold green]{option_text}[/bold green]")
            else:
                content.append(f"[green]{prefix}{option_text}[/green]")
    
    return "\n".join(content)

def edit_ws_uris_menu(console):
    """
    Interactive menu to edit WebSocket server URIs and tokens with adaptive layout.
    """
    # Load current URIs and tokens from configuration
    uris, tokens, _ = WebSocketConfig.get_ws_config()

    # Define menu options
    menu_options = [
        ("Add new URI", "add"),
        ("Edit existing URI", "edit"),
        ("Remove URI", "remove"),
        ("Save changes", "save"),
        ("Cancel", "cancel")
    ]
    
    selected_index = 0

    while True:
        clear_console()
        
        # Get current terminal size
        terminal_width, terminal_height = get_terminal_size()
        
        # Adjust layout based on terminal height
        if terminal_height < 20:
            # Small terminal - use single column layout
            layout = Layout()
            layout.split_column(
                Layout(create_uri_header(), name="header", size=3),
                Layout(name="main"),
                Layout(create_uri_footer(), name="footer", size=3)
            )
            
            # Create combined content for small screens
            table_content = create_uri_table_content(uris, tokens, terminal_width, terminal_height)
            menu_content = create_uri_menu_content(menu_options, selected_index, len(uris) > 0)
            
            combined_content = f"{table_content}\n\n{menu_content}"
            layout["main"].update(Panel(combined_content, style="white", padding=(0, 1)))
        else:
            # Normal terminal - use split layout
            layout = Layout()
            layout.split_column(
                Layout(create_uri_header(), name="header", size=3),
                Layout(name="main"),
                Layout(create_uri_footer(), name="footer", size=3)
            )
            
            # Split main area with better proportions
            available_height = terminal_height - 6  # Header + footer
            table_height = min(12, available_height // 2 + 2)  # Max 12 lines for table
            menu_height = available_height - table_height
            
            layout["main"].split_column(
                Layout(name="table", size=table_height),
                Layout(name="menu", size=menu_height)
            )
            
            # Create and add content
            table_content = create_uri_table_content(uris, tokens, terminal_width, terminal_height)
            menu_content = create_uri_menu_content(menu_options, selected_index, len(uris) > 0)
            
            layout["table"].update(Panel(table_content, style="white", padding=(0, 1)))
            layout["menu"].update(Panel(menu_content, style="white", padding=(0, 1)))
        
        # Print the layout without extra newlines
        with console.capture() as capture:
            console.print(layout, end="")
        
        # Print captured content and move cursor to avoid layout shifting
        print(capture.get(), end="", flush=True)
        
        # Handle keyboard input
        try:
            key = get_key()
            if key == 'up':
                selected_index = (selected_index - 1) % len(menu_options)
            elif key == 'down':
                selected_index = (selected_index + 1) % len(menu_options)
            elif key == 'enter':
                action = menu_options[selected_index][1]
                
                # Check if action is disabled
                if action in ["edit", "remove"] and not uris:
                    continue
                
                # Execute the selected action (clear console for forms)
                clear_console()
                
                if action == "add":
                    console.print("[bold cyan]Adding new WebSocket URI[/bold cyan]\n")
                    new_uri = Prompt.ask("[bold cyan]Enter new WebSocket URI")
                    new_token = Prompt.ask("[bold cyan]Enter token for this URI")
                    if new_uri:
                        uris.append(new_uri.strip())
                        tokens.append(new_token.strip())
                        console.print(f"[green]Added: {new_uri}[/green]")
                    input("\nPress Enter to continue...")

                elif action == "edit":
                    console.print("[bold cyan]Editing existing URI[/bold cyan]\n")
                    
                    # Show current URIs in a compact format
                    for idx, uri in enumerate(uris, 1):
                        display_uri = uri[:50] + "..." if len(uri) > 50 else uri
                        console.print(f"[cyan]{idx}.[/cyan] {display_uri}")
                    
                    try:
                        idx = int(Prompt.ask("[bold cyan]Enter index to edit", choices=[str(i) for i in range(1, len(uris)+1)])) - 1
                        new_uri = Prompt.ask(f"[bold cyan]Edit URI", default=uris[idx])
                        new_token = Prompt.ask(f"[bold cyan]Edit token", default=tokens[idx])
                        uris[idx] = new_uri.strip()
                        tokens[idx] = new_token.strip()
                        console.print(f"[green]Updated URI at index {idx + 1}[/green]")
                    except (ValueError, IndexError):
                        console.print("[red]Invalid selection[/red]")
                    input("\nPress Enter to continue...")

                elif action == "remove":
                    console.print("[bold cyan]Removing URI[/bold cyan]\n")
                    
                    # Show current URIs in a compact format
                    for idx, uri in enumerate(uris, 1):
                        display_uri = uri[:50] + "..." if len(uri) > 50 else uri
                        console.print(f"[cyan]{idx}.[/cyan] {display_uri}")
                    
                    try:
                        idx = int(Prompt.ask("[bold cyan]Enter index to remove", choices=[str(i) for i in range(1, len(uris)+1)])) - 1
                        removed_uri = uris.pop(idx)
                        removed_token = tokens.pop(idx)
                        display_removed = removed_uri[:50] + "..." if len(removed_uri) > 50 else removed_uri
                        console.print(f"[green]Removed: {display_removed}[/green]")
                    except (ValueError, IndexError):
                        console.print("[red]Invalid selection[/red]")
                    input("\nPress Enter to continue...")

                elif action == "save":
                    WebSocketConfig.save_ws_config(uris=uris, tokens=tokens)
                    console.print("[green]URIs and tokens saved to .env[/green]")
                    input("\nPress Enter to return to main menu...")
                    return

                elif action == "cancel":
                    console.print("[yellow]No changes saved.[/yellow]")
                    input("\nPress Enter to return to main menu...")
                    return
                    
            elif key == 'esc':
                clear_console()
                console.print("[yellow]No changes saved.[/yellow]")
                input("\nPress Enter to return to main menu...")
                return
                
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Exiting...[/bold yellow]")
            return
