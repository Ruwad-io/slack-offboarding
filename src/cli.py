"""
OffBoarding CLI — Beautiful terminal UI for cleaning up your Slack messages.

Usage:
    offboarding login          # Setup your Slack token
    offboarding scan           # Scan conversations and show message counts
    offboarding clean          # Interactive cleanup wizard
    offboarding clean --all    # Delete all DMs (with confirmation)
    offboarding nuke           # Full wipe — all DMs, no questions asked (jk, still confirms)
"""

import os
import sys
import time
import click
from pathlib import Path
from dotenv import load_dotenv

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.columns import Columns
from rich import box

from src.services.slack_cleaner import SlackCleaner, CleanupStats

console = Console()

# Config file for storing token
CONFIG_DIR = Path.home() / ".config" / "offboarding"
CONFIG_FILE = CONFIG_DIR / "config"

LOGO = """
 ██████  ███████ ███████ ██████   ██████   █████  ██████  ██████  ██ ███    ██  ██████
██    ██ ██      ██      ██   ██ ██    ██ ██   ██ ██   ██ ██   ██ ██ ████   ██ ██
██    ██ █████   █████   ██████  ██    ██ ███████ ██████  ██   ██ ██ ██ ██  ██ ██   ███
██    ██ ██      ██      ██   ██ ██    ██ ██   ██ ██   ██ ██   ██ ██ ██  ██ ██ ██    ██
 ██████  ██      ██      ██████   ██████  ██   ██ ██   ██ ██████  ██ ██   ████  ██████
"""


def get_token() -> str | None:
    """Get Slack token from config file, env var, or .env."""
    load_dotenv()

    # 1. Check env var
    token = os.environ.get("SLACK_TOKEN")
    if token:
        return token

    # 2. Check config file
    if CONFIG_FILE.exists():
        token = CONFIG_FILE.read_text().strip()
        if token:
            return token

    return None


def save_token(token: str):
    """Save token to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(token)
    CONFIG_FILE.chmod(0o600)


def get_cleaner() -> SlackCleaner:
    """Get an authenticated SlackCleaner or exit."""
    token = get_token()
    if not token:
        console.print()
        console.print("[red]No Slack token found.[/red]")
        console.print()
        console.print("Run [bold cyan]offboarding login[/bold cyan] to set up your token.")
        sys.exit(1)

    try:
        cleaner = SlackCleaner(token)
        _ = cleaner.user_name  # test auth
        return cleaner
    except Exception as e:
        console.print(f"\n[red]Authentication failed:[/red] {e}")
        console.print("Run [bold cyan]offboarding login[/bold cyan] to update your token.")
        sys.exit(1)


def print_banner():
    """Print the OffBoarding banner."""
    console.print(Text(LOGO, style="bold #6366F1"))
    console.print(
        "  [dim]Clean up your Slack before you leave.[/dim]\n"
    )


# ══════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════


@click.group()
def main():
    """OffBoarding — Clean up your Slack messages before you leave."""
    pass


@main.command()
def login():
    """Setup your Slack token."""
    print_banner()

    console.print(
        Panel(
            "[bold]How to get your Slack token:[/bold]\n\n"
            "1. Go to [link=https://api.slack.com/apps]api.slack.com/apps[/link]\n"
            "2. Create New App → From scratch\n"
            "3. Go to [bold]OAuth & Permissions[/bold]\n"
            "4. Add these User Token Scopes:\n"
            "   [cyan]im:history, im:read, chat:write, users:read[/cyan]\n"
            "   [cyan]mpim:history, mpim:read, groups:history, groups:read[/cyan]\n"
            "   [cyan]channels:history, channels:read[/cyan]\n"
            "\n"
            "   [dim]Optional (Business+/Enterprise, deletes others' DMs too):[/dim]\n"
            "   [cyan]admin.conversations:write[/cyan]\n"
            "5. Install to Workspace\n"
            "6. Copy the [bold]User OAuth Token[/bold] (starts with xoxp-)",
            title="[bold #6366F1]Slack App Setup[/bold #6366F1]",
            border_style="#6366F1",
            padding=(1, 2),
        )
    )

    console.print()
    token = Prompt.ask("[bold]Paste your User OAuth Token[/bold]")

    if not token.startswith("xoxp-"):
        console.print("[yellow]Warning: Token doesn't start with 'xoxp-'. Are you sure?[/yellow]")
        if not Confirm.ask("Continue anyway?"):
            return

    # Test the token
    with console.status("[bold #6366F1]Verifying token...", spinner="dots"):
        try:
            cleaner = SlackCleaner(token)
            name = cleaner.user_name
        except Exception as e:
            console.print(f"\n[red]Invalid token:[/red] {e}")
            return

    save_token(token)
    console.print(f"\n[green]Authenticated as [bold]{name}[/bold][/green]")
    console.print(f"[dim]Token saved to {CONFIG_FILE}[/dim]\n")
    console.print("Run [bold cyan]offboarding scan[/bold cyan] to see your conversations.")


@main.command()
def scan():
    """Scan your DM conversations and show message counts."""
    print_banner()

    cleaner = get_cleaner()
    console.print(f"[dim]Signed in as[/dim] [bold]{cleaner.user_name}[/bold]\n")

    # Fetch conversations
    with console.status("[bold #6366F1]Scanning conversations...", spinner="dots"):
        dms = cleaner.list_dm_conversations()

    if not dms:
        console.print("[yellow]No DM conversations found.[/yellow]")
        return

    # Count messages with progress bar
    table = Table(
        title=f"[bold]Your DM Conversations[/bold] ({len(dms)} total)",
        box=box.ROUNDED,
        border_style="#6366F1",
        header_style="bold #6366F1",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Conversation", style="bold")
    table.add_column("Your Messages", justify="right")
    table.add_column("Status", justify="center")

    total_messages = 0

    with Progress(
        SpinnerColumn(style="#6366F1"),
        TextColumn("[bold #6366F1]Counting messages..."),
        BarColumn(complete_style="#6366F1", finished_style="#10B981"),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        console=console,
    ) as progress:
        task = progress.add_task("Counting", total=len(dms))

        def on_counted(cid, count):
            progress.update(task, advance=1)

        counts = cleaner.count_my_messages_batch(
            [dm["id"] for dm in dms], on_each=on_counted
        )

    for i, dm in enumerate(dms, 1):
        count = counts.get(dm["id"], 0)
        total_messages += count
        status = "[green]clean[/green]" if count == 0 else f"[yellow]{count} msgs[/yellow]"
        table.add_row(str(i), dm["user_name"], str(count), status)

    console.print()
    console.print(table)
    console.print()

    # Summary
    with_messages = sum(1 for dm in dms if True)  # we'd need counts cached
    console.print(
        Panel(
            f"[bold]{total_messages}[/bold] messages across [bold]{len(dms)}[/bold] conversations",
            title="[bold]Summary[/bold]",
            border_style="#6366F1",
            padding=(0, 2),
        )
    )
    console.print()
    console.print(
        "Run [bold cyan]offboarding clean[/bold cyan] to start deleting.\n"
    )


@main.command()
@click.option("--all", "clean_all", is_flag=True, help="Delete all DMs without selecting.")
@click.option("--dry-run", is_flag=True, help="Simulate without deleting.")
def clean(clean_all: bool, dry_run: bool):
    """Interactive cleanup — select conversations to clean."""
    print_banner()

    cleaner = get_cleaner()
    console.print(f"[dim]Signed in as[/dim] [bold]{cleaner.user_name}[/bold]\n")

    if dry_run:
        console.print("[yellow]DRY RUN MODE — no messages will be deleted[/yellow]\n")

    # Fetch conversations
    with console.status("[bold #6366F1]Loading conversations...", spinner="dots"):
        dms = cleaner.list_dm_conversations()

    if not dms:
        console.print("[yellow]No DM conversations found.[/yellow]")
        return

    # Count messages (concurrent)
    with Progress(
        SpinnerColumn(style="#6366F1"),
        TextColumn("[bold #6366F1]Counting messages..."),
        BarColumn(complete_style="#6366F1", finished_style="#10B981"),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        console=console,
    ) as progress:
        task = progress.add_task("Counting", total=len(dms))

        def on_counted(cid, count):
            progress.update(task, advance=1)

        counts = cleaner.count_my_messages_batch(
            [dm["id"] for dm in dms], on_each=on_counted
        )

    dm_counts = [{**dm, "count": counts.get(dm["id"], 0)} for dm in dms]

    # Filter to conversations with messages
    with_messages = [d for d in dm_counts if d["count"] > 0]

    if not with_messages:
        console.print("\n[green]All clean! No messages to delete.[/green]")
        return

    console.print()

    if not clean_all:
        # Show conversations and let user pick
        table = Table(box=box.ROUNDED, border_style="#6366F1", header_style="bold #6366F1")
        table.add_column("#", style="dim", width=4)
        table.add_column("Conversation", style="bold")
        table.add_column("Messages", justify="right", style="yellow")

        for i, dm in enumerate(with_messages, 1):
            table.add_row(str(i), dm["user_name"], str(dm["count"]))

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "[bold]Which conversations to clean?[/bold]\n"
            "  [dim]Enter numbers (e.g. 1,3,5) or 'all'[/dim]",
            default="all",
        )

        if choice.lower() == "all":
            selected = with_messages
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected = [with_messages[i] for i in indices if 0 <= i < len(with_messages)]
            except (ValueError, IndexError):
                console.print("[red]Invalid selection.[/red]")
                return
    else:
        selected = with_messages

    # Confirm
    total_msgs = sum(d["count"] for d in selected)
    console.print()

    if not dry_run:
        console.print(
            Panel(
                f"[bold red]About to delete {total_msgs} messages "
                f"across {len(selected)} conversations.[/bold red]\n\n"
                "[dim]This action is irreversible.[/dim]",
                title="[bold red]Confirmation[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )

        if not Confirm.ask("\n[bold]Are you sure?[/bold]"):
            console.print("[dim]Cancelled.[/dim]")
            return

    # Delete with progress
    console.print()
    total_deleted = 0
    total_failed = 0

    with Progress(
        SpinnerColumn(style="#6366F1"),
        TextColumn("[bold]{task.description}"),
        BarColumn(complete_style="#6366F1", finished_style="#10B981"),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task(
            f"[#6366F1]Overall progress", total=total_msgs
        )

        for dm in selected:
            task = progress.add_task(
                f"  {dm['user_name']}", total=dm["count"]
            )

            messages = cleaner.get_my_messages(dm["id"])

            def on_progress(stats):
                progress.update(task, completed=stats.messages_deleted + stats.messages_failed)
                progress.update(overall, advance=1)

            stats = cleaner.delete_messages(
                dm["id"],
                messages=messages,
                dry_run=dry_run,
                on_progress=on_progress,
            )

            total_deleted += stats.messages_deleted
            total_failed += stats.messages_failed

            progress.update(task, completed=dm["count"])

    # Results
    console.print()
    action = "would be deleted" if dry_run else "deleted"

    result_style = "#10B981" if total_failed == 0 else "yellow"

    console.print(
        Panel(
            f"[bold green]{total_deleted}[/bold green] messages {action}\n"
            + (f"[bold red]{total_failed}[/bold red] failed\n" if total_failed else "")
            + f"[dim]{len(selected)} conversations processed[/dim]",
            title="[bold]Results[/bold]",
            border_style=result_style,
            padding=(1, 2),
        )
    )
    console.print()


@main.command()
@click.option("--dry-run", is_flag=True, help="Simulate without deleting.")
def nuke(dry_run: bool):
    """Full wipe — delete ALL your messages EVERYWHERE (DMs, group DMs, channels, threads)."""
    print_banner()

    cleaner = get_cleaner()
    console.print(f"[dim]Signed in as[/dim] [bold]{cleaner.user_name}[/bold]\n")

    if dry_run:
        console.print("[yellow]DRY RUN MODE — no messages will be deleted[/yellow]\n")

    console.print(
        Panel(
            "[bold red]NUCLEAR OPTION[/bold red]\n\n"
            "This will delete [bold]every single message[/bold] you've sent\n"
            "across [bold]ALL conversations[/bold]:\n\n"
            "  [red]•[/red] Direct messages (DMs)\n"
            "  [red]•[/red] Group DMs\n"
            "  [red]•[/red] Public & private channels\n"
            "  [red]•[/red] Thread replies\n\n"
            "[dim]There is no undo.[/dim]",
            title="[bold red]WARNING[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )

    if not dry_run:
        console.print()
        confirm_text = Prompt.ask(
            "[bold red]Type 'DELETE EVERYTHING' to confirm[/bold red]"
        )
        if confirm_text != "DELETE EVERYTHING":
            console.print("[dim]Cancelled. Good call.[/dim]")
            return

    console.print()

    with console.status("[bold #6366F1]Scanning all conversations...", spinner="dots"):
        conversations = cleaner.list_all_conversations()

    dm_count = sum(1 for c in conversations if c["type"] == "dm")
    group_count = sum(1 for c in conversations if c["type"] == "group_dm")
    chan_count = sum(1 for c in conversations if c["type"] == "channel")
    admin_mode = cleaner.can_delete_others

    console.print(
        f"  Found [bold]{dm_count}[/bold] DMs, "
        f"[bold]{group_count}[/bold] group DMs, "
        f"[bold]{chan_count}[/bold] channels"
    )
    if admin_mode:
        console.print(
            "  [bold yellow]Admin mode:[/bold yellow] will also delete "
            "[bold]other people's messages[/bold] in your DMs"
        )
    console.print()

    total_deleted = 0
    total_failed = 0

    with Progress(
        SpinnerColumn(style="#6366F1"),
        TextColumn("[bold]{task.description}"),
        BarColumn(complete_style="#6366F1", finished_style="#10B981"),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task(
            f"[#6366F1]Cleaning {len(conversations)} conversations", total=len(conversations)
        )

        for conv in conversations:
            # In admin mode, delete ALL messages in DMs (yours + theirs)
            if admin_mode and conv["type"] == "dm":
                messages = cleaner.get_all_messages(conv["id"])
            else:
                messages = cleaner.get_my_messages(conv["id"])

            if messages:
                conv_task = progress.add_task(
                    f"  {conv['user_name']}", total=len(messages)
                )

                def on_progress(stats, _task=conv_task):
                    progress.update(
                        _task, completed=stats.messages_deleted + stats.messages_failed
                    )

                stats = cleaner.delete_messages(
                    conv["id"],
                    messages=messages,
                    dry_run=dry_run,
                    on_progress=on_progress,
                )

                total_deleted += stats.messages_deleted
                total_failed += stats.messages_failed

            progress.update(overall, advance=1)

    console.print()
    action = "would be deleted" if dry_run else "deleted"

    console.print(
        Panel(
            f"[bold green]{total_deleted}[/bold green] messages {action}\n"
            + (f"[bold red]{total_failed}[/bold red] failed\n" if total_failed else "")
            + f"[dim]{len(conversations)} conversations scanned "
            + f"(DMs + group DMs + channels + threads)[/dim]",
            title="[bold]Mission Complete[/bold]",
            border_style="#10B981",
            padding=(1, 2),
        )
    )
    console.print("[dim]Goodbye. [/dim]\n")


@main.command()
def logout():
    """Remove saved Slack token."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        console.print("[green]Token removed.[/green]")
    else:
        console.print("[dim]No token found.[/dim]")


@main.command()
def status():
    """Check authentication status."""
    print_banner()

    token = get_token()
    if not token:
        console.print("[red]Not authenticated.[/red]")
        console.print("Run [bold cyan]offboarding login[/bold cyan] to set up.\n")
        return

    with console.status("[bold #6366F1]Checking connection...", spinner="dots"):
        try:
            cleaner = SlackCleaner(token)
            name = cleaner.user_name
            user_id = cleaner.user_id
        except Exception as e:
            console.print(f"[red]Token invalid:[/red] {e}")
            return

    console.print(
        Panel(
            f"[bold green]Connected[/bold green]\n\n"
            f"  User:  [bold]{name}[/bold]\n"
            f"  ID:    [dim]{user_id}[/dim]\n"
            f"  Token: [dim]{token[:12]}...{token[-4:]}[/dim]",
            title="[bold]Status[/bold]",
            border_style="#10B981",
            padding=(1, 2),
        )
    )
    console.print()


if __name__ == "__main__":
    main()
