import json
import os
import sys
from rich.console import Console
from rich.prompt import Prompt

from Remote import validation

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Core import dependency_manager as dep_manager
from Streams import stream_creation_db as stream_db
from npm import npm_handler as npmh
from Config import config as cfg

console = Console()

def add_streams_manually():
    """
    Allows manual addition of streams via interactive prompts.
    Includes configuration for IP-based access control.
    """
    console.rule("[bold blue]Add Streams Manually")

    try:
        import sqlite3

        # Check if NPM database exists and get user ID
        db_path = cfg.SQLITE_DB_PATH
        if not os.path.exists(db_path):
            console.print(
                "[bold red]NPM database not found. Please ensure NPM is running.[/bold red]")
            input("\nPress Enter to continue...")
            return

        # Retrieve the first user ID from the NPM database
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM user ORDER BY id LIMIT 1")
            user_row = cur.fetchone()
            if not user_row:
                console.print(
                    "[bold red]No user found in NPM database. Please set up NPM first.[/bold red]")
                input("\nPress Enter to continue...")
                return
            owner_user_id = user_row[0]
        finally:
            conn.close()

        # Prompt user for stream details
        incoming_port = Prompt.ask("[bold cyan]Enter incoming port")
        try:
            incoming_port = int(incoming_port)
        except ValueError:
            console.print("[bold red]Invalid port number[/bold red]")
            input("\nPress Enter to continue...")
            return

        forwarding_host = Prompt.ask(
            "[bold cyan]Enter forwarding host/IP", default="127.0.0.1")

        forwarding_port = Prompt.ask(
            "[bold cyan]Enter forwarding port", default=str(incoming_port))
        try:
            forwarding_port = int(forwarding_port)
        except ValueError:
            console.print(
                "[bold red]Invalid forwarding port number[/bold red]")
            input("\nPress Enter to continue...")
            return

        protocol = Prompt.ask("[bold cyan]Enter protocol", choices=[
                              "tcp", "udp", "both"], default="tcp")

        # NEW: IP Access Control Configuration
        console.print(
            "\n[bold yellow]🔒 IP Access Control Configuration[/bold yellow]")
        console.print(
            "[bold cyan]Configure which IPs can access this stream (leave empty for no restrictions)[/bold cyan]")

        enable_access_control = Prompt.ask(
            "[bold cyan]Enable IP access control?[/bold cyan]",
            choices=["yes", "no"],
            default="no"
        )

        allowed_ips = []
        denied_ips = []

        if enable_access_control == "yes":
            console.print("\n[bold green]📝 Access Control Rules:[/bold green]")
            console.print(
                "[bold white]• Allowed IPs: Connections from these IPs will be accepted[/bold white]")
            console.print(
                "[bold white]• Denied IPs: Connections from these IPs will be blocked[/bold white]")
            console.print(
                "[bold white]• If no allowed IPs are specified, all IPs are allowed except denied ones[/bold white]")
            console.print(
                "[bold white]• If allowed IPs are specified, only those IPs are allowed (plus denied rules apply)[/bold white]")

            # Prompt for allowed IPs
            allowed_ips_input = Prompt.ask(
                "\n[bold green]Enter allowed IPs (comma-separated, e.g., 192.168.1.10,203.0.113.0/24)[/bold green]",
                default=""
            )

            if allowed_ips_input.strip():
                allowed_ips = [ip.strip()
                               for ip in allowed_ips_input.split(",") if ip.strip()]
                console.print(
                    f"[bold green]✅ Allowed IPs: {', '.join(allowed_ips)}[/bold green]")

            # Prompt for denied IPs
            denied_ips_input = Prompt.ask(
                "\n[bold red]Enter denied IPs (comma-separated, e.g., 10.0.0.0/8,172.16.0.0/12)[/bold red]",
                default=""
            )

            if denied_ips_input.strip():
                denied_ips = [ip.strip()
                              for ip in denied_ips_input.split(",") if ip.strip()]
                console.print(
                    f"[bold red]🚫 Denied IPs: {', '.join(denied_ips)}[/bold red]")

            # Validate IP formats
            invalid_ips = []
            all_ips = allowed_ips + denied_ips

            for ip in all_ips:
                if not validation._validate_ip_or_cidr(ip):
                    invalid_ips.append(ip)

            if invalid_ips:
                console.print(
                    f"[bold red]❌ Invalid IP addresses/ranges: {', '.join(invalid_ips)}[/bold red]")
                console.print(
                    "[bold yellow]Please check the format. Valid examples:[/bold yellow]")
                console.print(
                    "[bold white]• Single IP: 192.168.1.10[/bold white]")
                console.print(
                    "[bold white]• CIDR range: 192.168.1.0/24[/bold white]")
                console.print("[bold white]• IPv6: 2001:db8::1[/bold white]")
                input("\nPress Enter to continue...")
                return

            # Show access control summary
            console.print("\n[bold cyan]📋 Access Control Summary:[/bold cyan]")
            if allowed_ips:
                console.print(
                    f"[bold green]✅ Allowed: {len(allowed_ips)} IP(s)/range(s)[/bold green]")
                for ip in allowed_ips:
                    console.print(f"[bold white]   • {ip}[/bold white]")
            else:
                console.print(
                    "[bold green]✅ Allowed: All IPs (no restrictions)[/bold green]")

            if denied_ips:
                console.print(
                    f"[bold red]🚫 Denied: {len(denied_ips)} IP(s)/range(s)[/bold red]")
                for ip in denied_ips:
                    console.print(f"[bold white]   • {ip}[/bold white]")
            else:
                console.print("[bold yellow]🚫 Denied: None[/bold yellow]")

        # Create or update stream entries directly in the database
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()

            # Prepare access list metadata
            access_list_config = {
                "enabled": enable_access_control == "yes",
                "allowed_ips": allowed_ips,
                "denied_ips": denied_ips
            }

            default_meta = json.dumps({
                "dns_provider_credentials": "",
                "letsencrypt_agree": False,
                "dns_challenge": True,
                "nginx_online": True,
                "nginx_err": None,
                "access_list": access_list_config  # NEW: Store access control config
            })

            tcp_flag = 1 if protocol in ["tcp", "both"] else 0
            udp_flag = 1 if protocol in ["udp", "both"] else 0

            # Check if stream already exists
            cur.execute(
                "SELECT id FROM stream WHERE incoming_port=? AND is_deleted=0", (incoming_port,))
            existing = cur.fetchone()

            if existing:
                stream_id = existing[0]
                cur.execute(
                    "UPDATE stream SET forwarding_host=?, forwarding_port=?, tcp_forwarding=?, udp_forwarding=?, meta=?, modified_on=datetime('now') WHERE id=?",
                    (forwarding_host, forwarding_port, tcp_flag,
                     udp_flag, default_meta, stream_id)
                )
                console.print(
                    f"[bold green]✅ Updated existing stream {stream_id}[/bold green]")
            else:
                cur.execute(
                    "INSERT INTO stream (owner_user_id, incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, enabled, created_on, modified_on, meta) VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'), ?)",
                    (owner_user_id, incoming_port, forwarding_host,
                     forwarding_port, tcp_flag, udp_flag, default_meta)
                )
                console.print(f"[bold green]✅ Created new stream[/bold green]")

            conn.commit()

            # Sync configuration to apply access control rules
            try:
                stream_db.sync_streams_conf_with_sqlite()
                console.print(
                    "[bold green]✅ NGINX configuration updated with access control rules[/bold green]")

                # Reload NPM if available
                missing_deps = dep_manager.get_missing_dependencies()
                if "docker" not in missing_deps and "docker-compose" not in missing_deps:
                    npmh.reload_npm()
                    console.print(
                        "[bold green]✅ NPM reloaded to apply new configuration[/bold green]")

            except Exception as e:
                console.print(
                    f"[bold yellow]⚠️ Stream created but configuration sync failed: {e}[/bold yellow]")

            # Show final stream configuration summary
            console.print(
                f"\n[bold green]🎉 Stream configuration complete![/bold green]")
            console.print(f"[bold cyan]📝 Stream details:[/bold cyan]")
            console.print(
                f"[bold white]• Port: {incoming_port} → {forwarding_host}:{forwarding_port}[/bold white]")
            console.print(
                f"[bold white]• Protocol: {protocol.upper()}[/bold white]")
            if enable_access_control == "yes":
                console.print(
                    f"[bold white]• Access Control: Enabled[/bold white]")
                if allowed_ips:
                    console.print(
                        f"[bold white]• Allowed IPs: {len(allowed_ips)} configured[/bold white]")
                if denied_ips:
                    console.print(
                        f"[bold white]• Denied IPs: {len(denied_ips)} configured[/bold white]")
            else:
                console.print(
                    f"[bold white]• Access Control: Disabled (all IPs allowed)[/bold white]")

        finally:
            conn.close()

    except Exception as e:
        console.print(f"[bold red]Error adding stream: {e}[/bold red]")

    input("\nPress Enter to continue...")