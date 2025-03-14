"""The interactive terminal menu for video downloading.

Only asks questions and draws results. The decisions live in `formats`, the
fetching in `download`, and the banner and card menu are shared with the image
toolkit.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from shared.chrome import choose_from_cards, print_banner
from shared.format import human_bytes, human_duration
from shared.prompts import STYLE, Cancelled, ask as _ask
from shared.prompts import ask_path as _shared_ask_path
from shared.prompts import pause as _pause

from .download import OK, download, ffmpeg_available, probe
from .formats import AUDIO, VIDEO, quality_warning, readable_formats
from .planning import OPERATIONS, QUALITY_PRESETS, QUIT, READ_ONLY, menu_items
from .urls import clean_url

console = Console()

TITLE = "VID TOOLKIT"
SUBTITLE = "download  ·  audio only  ·  formats"
ACCENT = "#00d6aa"


def _banner() -> None:
    print_banner(console, TITLE, SUBTITLE)


def _choose_operation() -> str:
    chosen = choose_from_cards(console, menu_items(), "What would you like to do?")
    picked = next(item for item in menu_items() if item.key == chosen)
    console.print(f"[#00b894]?[/#00b894] [bold]Operation:[/bold] [#0984e3]{picked.title}[/#0984e3]")
    return chosen


def _ask_url() -> str:
    while True:
        raw = _ask(questionary.text("Link:", style=STYLE))
        try:
            return clean_url(raw)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")


def _info_panel(info) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Title", f"[bold]{info.title or '—'}[/bold]")
    if info.uploader:
        table.add_row("From", info.uploader)
    if info.duration:
        table.add_row("Length", human_duration(info.duration))
    if info.is_playlist:
        table.add_row("Playlist", f"[yellow]{info.entries} videos[/yellow]")
    return Panel(table, title="Found", border_style=ACCENT, title_align="left")


def _formats_table(rows: list[dict]) -> None:
    if not rows:
        console.print("[yellow]No formats reported for that link.[/yellow]\n")
        return

    table = Table(box=box.SIMPLE, header_style="bold", padding=(0, 1))
    for column in ("ID", "Ext", "Resolution", "FPS", "Size", "Contains"):
        table.add_column(column, justify="right" if column in ("FPS", "Size") else "left")
    for row in rows:
        table.add_row(row["id"], row["ext"], row["resolution"], row["fps"], row["size"], row["kind"])
    console.print(table)
    console.print(f"  [dim]{len(rows)} formats.[/dim]\n")


def _download_with_progress(url: str, dest_dir: Path, mode: str, max_height: int | None, ffmpeg: bool):
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TextColumn("{task.fields[rate]}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading", total=100, rate="")

        def on_progress(update) -> None:
            rate = f"{human_bytes(update.speed)}/s" if update.speed else ""
            if update.percent is not None:
                progress.update(task, completed=update.percent, rate=rate)
            else:
                progress.update(task, rate=f"{human_bytes(update.downloaded)} {rate}")
            if update.finished:
                progress.update(task, completed=100, description="Merging" if ffmpeg else "Done")

        result = download(
            url, dest_dir, mode=mode, max_height=max_height,
            ffmpeg=ffmpeg, on_progress=on_progress,
        )
        progress.update(task, completed=100, description="Done")
    return result


def _one_round() -> bool:
    operation = _choose_operation()
    if operation == QUIT:
        return False

    ffmpeg = ffmpeg_available()
    warning = quality_warning(ffmpeg)
    if warning and operation != "formats":
        console.print(f"  [yellow]{warning}[/yellow]\n")

    url = _ask_url()

    with console.status("[dim]Looking it up…[/dim]", spinner="dots"):
        info = probe(url)

    if info.error:
        console.print(f"  [red]Could not read that link.[/red]\n  [dim]{info.error}[/dim]\n")
        _pause()
        return True

    console.print(_info_panel(info))

    if operation in READ_ONLY:
        _formats_table(readable_formats({"formats": info.formats or []}))
        _pause()
        return True

    mode = AUDIO if operation == "audio" else VIDEO
    max_height = None
    if mode == VIDEO:
        max_height = _ask(
            questionary.select(
                "Quality:",
                choices=[Choice(label, height) for label, height in QUALITY_PRESETS],
                style=STYLE,
            )
        )

    dest_dir = _shared_ask_path(console, "Save to:", default=str(Path.home() / "Downloads"))

    count = info.entries if info.is_playlist else 1
    noun = "video" if count == 1 else "videos"
    if not _ask(questionary.confirm(f"Download {count} {noun}?", default=True, style=STYLE)):
        console.print("[dim]Cancelled.[/dim]\n")
        return True

    result = _download_with_progress(url, dest_dir, mode, max_height, ffmpeg)

    if result.status == OK:
        console.print(f"\n  [green]Saved[/green]  {human_bytes(result.size_bytes)}")
        console.print(f"  [bold]{result.path}[/bold]\n")
    else:
        console.print(f"\n  [red]Failed.[/red]  [dim]{result.detail}[/dim]\n")

    _pause()
    return True


def main() -> int:
    _banner()
    try:
        while _one_round():
            pass
    except Cancelled:
        console.print("\n[dim]Cancelled.[/dim]")
        return 130
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        return 130
    console.print("[dim]Bye.[/dim]")
    return 0
