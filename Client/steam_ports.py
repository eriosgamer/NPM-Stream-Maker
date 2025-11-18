from rich.console import Console
from rich.progress import Progress
from UI.console_handler import ws_info, ws_error

console = Console()

# This module provides a function to generate a set of common ports used by Steam and popular game servers.
# The list covers a wide range of games and services, expanding each base port for multiple instances.


def get_common_steam_ports():
    """
    Returns a set of common ports used by Steam and popular game servers.
    Expands the base ports to cover multiple game instances.
    """
    # List of tuples: (base_port, count, description)
    # Each tuple means: expand base_port for 'count' instances
    game_ports = [
        # Steam Core Services
        (27015, 32, "Source Dedicated Server (CS:GO, TF2, Garry's Mod, etc.)"),
        (27020, 16, "Source Engine RCON"),
        (27005, 16, "Source Engine Client"),
        (27000, 32, "Steam Client/Matchmaking"),
        (27030, 16, "Steam Remote Play"),
        (27036, 8, "Steam P2P Voice Chat"),
        (27050, 16, "Steam Content Servers"),
        (26900, 32, "Steam Client UDP"),
        # Popular Game Servers
        (7777, 16, "ARK: Survival Evolved, Terraria, Unreal Engine"),
        (7778, 16, "ARK: Survival Evolved Query Port"),
        (27016, 16, "Unreal Tournament, Killing Floor"),
        (28015, 16, "Rust Game Port"),
        (28016, 16, "Rust RCON Port"),
        (25565, 32, "Minecraft Java Edition"),
        (19132, 16, "Minecraft Bedrock Edition"),
        (2456, 16, "Valheim Game Port"),
        (2457, 16, "Valheim Query Port"),
        (2458, 16, "Valheim Query Port 2"),
        (8766, 8, "Satisfactory"),
        (15777, 8, "Satisfactory Query"),
        (16567, 16, "DayZ"),
        (8080, 16, "Various Web Admin Panels"),
        (8081, 16, "Various Web Admin Panels Alt"),
        (3724, 8, "World of Warcraft"),
        (6112, 16, "Warcraft III, StarCraft"),
        (1935, 8, "RTMP Streaming"),
        (27888, 8, "Conan Exiles"),
        (7778, 8, "OpenTTD"),
        (3979, 8, "OpenTTD Admin"),
        (64738, 8, "Mumble"),
        (25575, 16, "Minecraft RCON"),
        (19132, 16, "Minecraft PE/Bedrock"),
        (25566, 16, "Minecraft Additional Instances"),
        (24454, 8, "Core Keeper"),
        # FiveM and RedM (GTA/RDR servers)
        (30120, 32, "FiveM/RedM Game Port"),
        (30110, 32, "FiveM/RedM Alternate"),
        (30100, 32, "FiveM/RedM Additional"),
        # Battlefield Series
        (25200, 16, "Battlefield 1942"),
        (29900, 16, "Battlefield Vietnam"),
        (17567, 16, "Battlefield 2"),
        (48888, 16, "Battlefield 2142"),
        (19567, 16, "Battlefield Bad Company 2"),
        (25200, 16, "Battlefield 3"),
        (47200, 16, "Battlefield 4"),
        # Call of Duty Series
        (28960, 16, "Call of Duty"),
        (28950, 16, "Call of Duty 2"),
        (28970, 16, "Call of Duty 4"),
        (28961, 16, "Call of Duty: World at War"),
        (27014, 16, "Call of Duty: Modern Warfare 2"),
        # Counter-Strike
        (27015, 32, "Counter-Strike: Source/GO"),
        (27020, 16, "Counter-Strike RCON"),
        (27005, 16, "Counter-Strike Client"),
        # Garry's Mod and Source Mods
        (27015, 32, "Garry's Mod"),
        (27005, 16, "Garry's Mod Client"),
        # Left 4 Dead Series
        (27015, 16, "Left 4 Dead/L4D2"),
        # Team Fortress 2
        (27015, 16, "Team Fortress 2"),
        # Half-Life Series
        (27015, 16, "Half-Life 2: Deathmatch"),
        (27016, 8, "Half-Life Deathmatch: Source"),
        # Quake Series
        (27500, 16, "QuakeWorld"),
        (27910, 16, "Quake II"),
        (27960, 16, "Quake III Arena"),
        (27950, 16, "Quake 4"),
        # Unreal Tournament Series
        (7777, 16, "Unreal Tournament"),
        (7778, 8, "Unreal Tournament Query"),
        (7787, 8, "Unreal Tournament Web Admin"),
        # DOOM Series
        (5029, 8, "DOOM 3"),
        (27666, 8, "DOOM (2016)"),
        # Racing Games
        (63392, 8, "rFactor"),
        (34297, 8, "rFactor 2"),
        (9600, 8, "Assetto Corsa"),
        (9615, 8, "Assetto Corsa Competizione"),
        # Survival Games
        (27015, 16, "The Forest"),
        (8766, 8, "Raft"),
        (25444, 8, "Green Hell"),
        (7777, 8, "Astroneer"),
        # Strategy Games
        (2300, 16, "Age of Empires II"),
        (6500, 8, "Empire Earth"),
        (2302, 16, "Halo"),
        (9777, 8, "Supreme Commander"),
        # MMO Games
        (7777, 8, "Lineage II"),
        (2593, 8, "Ultima Online"),
        (5121, 8, "Neverwinter Nights"),
        (1024, 8, "Star Wars Galaxies"),
        # Sports Games
        (8888, 8, "FIFA"),
        (47624, 8, "PES"),
        # Space Games
        (14242, 8, "Space Engineers"),
        (27016, 8, "Kerbal Space Program"),
        # Indie/Other Popular Games
        (34197, 8, "Factorio"),
        (7777, 8, "Don't Starve Together"),
        (10999, 8, "Stardew Valley"),
        (24642, 8, "Rising World"),
        (15636, 8, "Eco"),
        (7777, 8, "Project Zomboid"),
        (16261, 8, "Project Zomboid Steam"),
        # Voice Chat Applications
        (9987, 8, "TeamSpeak 3 Voice"),
        (10011, 8, "TeamSpeak 3 ServerQuery"),
        (30033, 8, "TeamSpeak 3 File Transfer"),
        (8767, 8, "TeamSpeak 2"),
        (64738, 8, "Mumble"),
        (3478, 8, "Ventrilo"),
        # Streaming and Media
        (1935, 8, "RTMP (OBS, etc.)"),
        (8554, 8, "RTSP"),
        (554, 8, "RTSP Standard"),
        (1194, 8, "OpenVPN"),
        # Game Launchers and Tools
        (8393, 8, "GameSpy Arcade"),
        (6667, 8, "GameSpy IRC"),
        (27900, 8, "Nintendo WiFi Connection"),
        # Emulated Console Games
        (6500, 8, "Dolphin Netplay (GameCube/Wii)"),
        (7777, 8, "PCSX2 Netplay (PS2)"),
        (55435, 8, "Parsec"),
        # Game Development/Testing
        (7979, 8, "Unity Multiplayer"),
        (8888, 8, "Unreal Engine 4/5"),
        (3333, 8, "GameMaker Studio"),
        # Additional Ranges for Growth
        (20000, 32, "Custom Game Servers Range 1"),
        (30000, 32, "Custom Game Servers Range 2"),
        (40000, 32, "Custom Game Servers Range 3"),
        (50000, 32, "Custom Game Servers Range 4"),
        # Common Alternative Ports
        (8000, 16, "HTTP Alternate"),
        (8443, 8, "HTTPS Alternate"),
        (9000, 16, "Various Services"),
        (10000, 16, "Various Services"),
        (20000, 16, "Various Services"),
        # Docker and Container Common Ports
        (3000, 16, "Node.js/React Dev Servers"),
        (4000, 16, "Development Servers"),
        (5000, 16, "Flask/Development Servers"),
        (6000, 16, "Development Servers"),
        # Database Ports (for game backends)
        (3306, 8, "MySQL"),
        (5432, 8, "PostgreSQL"),
        (6379, 8, "Redis"),
        (27017, 8, "MongoDB"),
        # Additional High-Use Ranges
        (60000, 32, "Dynamic Allocation Range"),
        (61000, 32, "Dynamic Allocation Range"),
        (62000, 32, "Dynamic Allocation Range"),
        (63000, 32, "Dynamic Allocation Range"),
    ]

    ports = set()
    # Calculate the total number of port combinations to be generated
    total_combinations = sum(count for _, count, _ in game_ports)
    ws_info(
        "[WS_CLIENT]",
        f"Generating {total_combinations} game server ports from {len(game_ports)} categories...",
    )

    # Use a progress bar to show progress while generating ports
    with Progress() as progress:
        task = progress.add_task(
            "[cyan]Generating port combinations...", total=len(game_ports)
        )

        for base, count, description in game_ports:
            for i in range(count):
                ports.add(base + i)
            progress.advance(task)

    ws_info("[WS_CLIENT]", f"Generated {len(ports)} unique game server ports")
    return ports


# --- Module summary ---
# This file provides a function to generate a comprehensive set of ports for Steam and game servers.
# It is useful for scanning, firewall configuration, or automated port management in gaming environments.
