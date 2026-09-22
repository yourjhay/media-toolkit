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
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from shared.chrome import choose_from_cards, print_banner
from shared.format import human_bytes, human_duration
from shared.prompts import STYLE, Cancelled, GoBack
from shared.prompts import ask as _ask
from shared.prompts import ask_text_or_back
from shared.prompts import ask_path as _shared_ask_path
from shared.prompts import pause as _pause
from shared.settings import recall_path, remember_path

from .containers import playback_warning, plan_conversion, supported_targets
from .download import OK as DOWNLOAD_OK
from .download import download, ffmpeg_available, probe
from .failures import failure_hint, is_transient
from .media import probe_media
from .operations import OK as ENCODE_OK
from .operations import OVER, SKIPPED
from .tasks import compress_video, convert_video, trim_video
from .timecode import format_timecode, parse_timecode
from .formats import AUDIO, MP3, VIDEO, quality_warning, readable_formats
from .planning import (
    LOCAL,
    SIZE_PRESETS,
    VIDEO_SUFFIXES,
    QUALITY_PRESETS,
    QUIT,
    READ_ONLY,
    download_noun,
    menu_items,
)
from .urls import clean_url

console = Console()

TITLE = "VID TOOLKIT"
SUBTITLE = "download  ·  audio only  ·  formats"
ACCENT = "#00d6aa"


DOWNLOAD_DEST = "video.download.dest"
LOCAL_DEST = "video.local.dest"


def _ask_dest(key: str, fallback: Path) -> Path:
    """Ask where to save, offering wherever they said last time.

    Typing the same folder on every run is the sort of small friction that
    makes a tool tiring, so the answer is kept between sessions.
    """
    chosen = _shared_ask_path(console, "Save to:", default=str(recall_path(key, fallback)))
    remember_path(key, chosen)
    return chosen


def progress_bar() -> Progress:
    """The one progress display, shared by downloading and encoding.

    The spinner leads it because both jobs spend their opening seconds with no
    percentage to show — yt-dlp resolving a link, ffmpeg opening a file — and a
    bar sitting at zero with nothing moving looks like a hang.
    """
    return Progress(
        SpinnerColumn(finished_text="[green]done[/green]"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TextColumn("{task.fields[rate]}"),
        TimeRemainingColumn(),
        console=console,
    )


def _banner() -> None:
    print_banner(console, TITLE, SUBTITLE)


def _choose_operation() -> str:
    chosen = choose_from_cards(console, menu_items(), "What would you like to do?")
    picked = next(item for item in menu_items() if item.key == chosen)
    console.print(f"[#00b894]?[/#00b894] [bold]Operation:[/bold] [#0984e3]{picked.title}[/#0984e3]")
    return chosen


def _ask_url() -> str:
    while True:
        try:
            return clean_url(ask_text_or_back("Link:"))
        except GoBack:
            raise
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


def _ask_audio_conversion(ffmpeg: bool) -> tuple[str | None, bool]:
    """Whether to convert the downloaded audio, and whether to keep the source.

    Sites commonly serve their best audio as opus in a webm container. It
    plays, but it is not what most people expect an audio file to be.
    """
    if not ffmpeg:
        console.print(
            "  [yellow]Converting needs ffmpeg, which is not installed. "
            "Run  brew install ffmpeg  to enable it.[/yellow]\n"
        )
        return None, False

    if not _ask(questionary.confirm("Convert to MP3?", default=True, style=STYLE)):
        return None, False

    keep = _ask(
        questionary.confirm(
            "Keep the original file as well?", default=False, style=STYLE
        )
    )
    return MP3, keep


def _download_with_progress(
    url: str,
    dest_dir: Path,
    mode: str,
    max_height: int | None,
    ffmpeg: bool,
    convert_to: str | None = None,
    keep_original: bool = False,
    label: str = "Downloading",
):
    with progress_bar() as progress:
        task = progress.add_task(label, total=100, rate="")

        def on_progress(update) -> None:
            rate = f"{human_bytes(update.speed)}/s" if update.speed else ""
            if update.percent is not None:
                progress.update(task, completed=update.percent, rate=rate)
            else:
                progress.update(task, rate=f"{human_bytes(update.downloaded)} {rate}")
            if update.finished:
                after = "Converting" if convert_to else ("Merging" if ffmpeg else "Done")
                progress.update(task, completed=100, description=after)

        result = download(
            url, dest_dir, mode=mode, max_height=max_height, ffmpeg=ffmpeg,
            convert_to=convert_to, keep_original=keep_original,
            on_progress=on_progress,
        )
        progress.update(task, completed=100, description="Done")
    return result


def _media_panel(info) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("File", f"[bold]{info.path.name}[/bold]")
    table.add_row("Size", human_bytes(info.size_bytes))
    if info.duration:
        table.add_row("Length", human_duration(info.duration))
    table.add_row("Picture", f"{info.resolution}   {info.video_codec or '—'}")
    table.add_row("Sound", info.audio_codec or "[dim]none[/dim]")
    table.add_row("Where", str(info.path.parent))
    return Panel(table, title="Source", border_style=ACCENT, title_align="left")


def _ask_media_file() -> "object":
    while True:
        path = _shared_ask_path(console, "Video file:")
        if not path.is_file():
            console.print(f"[red]No such file:[/red] {path}\n")
            continue
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            console.print(f"[yellow]{path.suffix or 'That'} is not a video this handles.[/yellow]\n")
            continue
        with console.status("[dim]Reading it…[/dim]", spinner="dots"):
            info = probe_media(path)
        if info.error:
            console.print(f"[red]Could not read it.[/red] [dim]{info.error}[/dim]\n")
            continue
        return info


def _ask_target_size() -> int:
    choices = [Choice(label, size) for label, size in SIZE_PRESETS]
    choices.append(Choice("Something else", None))
    chosen = _ask(questionary.select("Shrink to:", choices=choices, style=STYLE))
    if chosen is not None:
        return chosen
    megabytes = _ask_int_mb()
    return megabytes * 1024 * 1024


def _ask_int_mb() -> int:
    from shared.prompts import ask_int

    return ask_int("Target size in MB:", 25, 1, 100_000)


def _ask_trim_range(info):
    def ask_time(message: str, default: str) -> float:
        while True:
            raw = _ask(questionary.text(message, default=default, style=STYLE))
            try:
                return parse_timecode(raw)
            except ValueError as exc:
                console.print(f"[red]{exc}[/red]")

    start = ask_time("Start at (m:ss):", "0:00")
    end = ask_time("End at (m:ss):", format_timecode(info.duration or 0))
    precise = not _ask(
        questionary.confirm(
            "Fast cut? (instant, but snaps to the nearest keyframe)",
            default=True, style=STYLE,
        )
    )
    return start, end, precise


def _run_encode(describe: str, info, work):
    with progress_bar() as progress:
        task = progress.add_task(describe, total=100, rate="")

        def on_progress(update) -> None:
            rate = f"{update.speed:.1f}x" if update.speed else ""
            if update.percent is not None:
                progress.update(task, completed=update.percent, rate=rate)
            else:
                progress.update(task, rate=rate)

        result = work(on_progress)
        progress.update(task, completed=100, description="Done")
    return result


def _local_round(operation: str, ffmpeg: bool) -> bool:
    if not ffmpeg:
        console.print(
            "  [red]This needs ffmpeg, which is not installed.[/red]\n"
            "  [dim]Run  brew install ffmpeg  and try again.[/dim]\n"
        )
        _pause()
        return True

    info = _ask_media_file()
    console.print(_media_panel(info))

    if operation == "convert":
        target = _ask(
            questionary.select(
                "Convert to:",
                choices=[Choice(ext.upper(), ext) for ext in supported_targets()],
                style=STYLE,
            )
        )
        force = False
        warning = playback_warning(info.video_codec, target)
        if warning:
            console.print(f"  [yellow]{warning}[/yellow]\n")
            force = _ask(
                questionary.select(
                    "Video:",
                    choices=[
                        Choice("Re-encode to H.264  —  plays everywhere", True),
                        Choice("Copy as-is  —  instant and lossless, may not play", False),
                    ],
                    style=STYLE,
                )
            )

        plan = plan_conversion(
            info.video_codec, info.audio_codec, target,
            hardware=True, force_video_encode=force,
        )
        if plan.lossless:
            console.print("  [green]Repackage only — instant, and the video is untouched.[/green]")
        else:
            console.print(f"  [yellow]Re-encoding needed.[/yellow] [dim]{plan.reason}[/dim]")
        console.print()
        describe = f"Converting to {target}"
        settings = {"target_ext": target, "force_video_encode": force}

    elif operation == "compress":
        target_bytes = _ask_target_size()
        describe = f"Compressing to {human_bytes(target_bytes)}"
        settings = {"target_bytes": target_bytes}

    else:
        start, end, precise = _ask_trim_range(info)
        describe = "Trimming"
        settings = {"start": start, "end": end, "precise": precise}

    dest_dir = _ask_dest(LOCAL_DEST, info.path.parent / "converted")

    if not _ask(questionary.confirm("Go ahead?", default=True, style=STYLE)):
        console.print("[dim]Cancelled.[/dim]\n")
        return True

    runners = {"convert": convert_video, "compress": compress_video, "trim": trim_video}

    def work(hook):
        return runners[operation](info.path, dest_dir, on_progress=hook, **settings)

    result = _run_encode(describe, info, work)

    if result.status == ENCODE_OK:
        console.print(f"\n  [green]Saved[/green]  {human_bytes(result.output_bytes)}"
                      f"  [dim](from {human_bytes(result.source_bytes)})[/dim]")
        console.print(f"  [bold]{result.output}[/bold]")
        console.print(f"  [dim]{result.detail}[/dim]\n")
    elif result.status == OVER:
        console.print(f"\n  [yellow]Done, but over target.[/yellow] [dim]{result.detail}[/dim]")
        console.print(f"  [bold]{result.output}[/bold]\n")
    elif result.status == SKIPPED:
        console.print(f"\n  [dim]Skipped: {result.detail}[/dim]\n")
    else:
        console.print(f"\n  [red]Failed.[/red] [dim]{result.detail}[/dim]\n")

    _pause()
    return True


def _one_round() -> bool:
    operation = _choose_operation()
    if operation == QUIT:
        return False

    ffmpeg = ffmpeg_available()

    if operation in LOCAL:
        return _local_round(operation, ffmpeg)

    warning = quality_warning(ffmpeg)
    if warning and operation != "formats":
        console.print(f"  [yellow]{warning}[/yellow]\n")

    url = _ask_url()

    while True:
        with console.status("[dim]Looking it up…[/dim]", spinner="dots"):
            info = probe(url)
        if not info.error:
            break

        console.print(f"  [red]Could not read that link.[/red]\n  [dim]{info.error}[/dim]")
        hint = failure_hint(info.error)
        if hint:
            console.print(f"  [dim]{hint}[/dim]")
        console.print()

        if not _ask(
            questionary.confirm(
                "Try again?", default=is_transient(info.error), style=STYLE
            )
        ):
            _pause()
            return True

    console.print(_info_panel(info))

    if operation in READ_ONLY:
        _formats_table(readable_formats({"formats": info.formats or []}))
        _pause()
        return True

    mode = AUDIO if operation == "audio" else VIDEO
    convert_to, keep_original = (None, False)
    max_height = None
    if mode == AUDIO:
        convert_to, keep_original = _ask_audio_conversion(ffmpeg)
    if mode == VIDEO:
        max_height = _ask(
            questionary.select(
                "Quality:",
                choices=[Choice(label, height) for label, height in QUALITY_PRESETS],
                style=STYLE,
            )
        )

    dest_dir = _ask_dest(DOWNLOAD_DEST, Path.home() / "Downloads")

    count = info.entries if info.is_playlist else 1
    if not _ask(
        questionary.confirm(
            f"Download {download_noun(mode, count)}?", default=True, style=STYLE
        )
    ):
        console.print("[dim]Cancelled.[/dim]\n")
        return True

    attempt = 0
    while True:
        attempt += 1
        label = "Downloading" if attempt == 1 else f"Retrying (attempt {attempt})"
        result = _download_with_progress(
            url, dest_dir, mode, max_height, ffmpeg, convert_to, keep_original, label
        )
        if result.status == DOWNLOAD_OK:
            break

        console.print(f"\n  [red]Failed.[/red] [dim]{result.detail}[/dim]")
        hint = failure_hint(result.detail)
        if hint:
            console.print(f"  [dim]{hint}[/dim]")
        console.print()

        worth_it = is_transient(result.detail)
        if not _ask(
            questionary.confirm("Try again?", default=worth_it, style=STYLE)
        ):
            break

    if result.status == DOWNLOAD_OK:
        console.print(f"\n  [green]Saved[/green]  {human_bytes(result.size_bytes)}")
        console.print(f"  [bold]{result.path}[/bold]")
        if convert_to and keep_original:
            console.print("  [dim]The original download was kept alongside it.[/dim]")
        console.print()
    else:
        console.print(f"\n  [red]Failed.[/red]  [dim]{result.detail}[/dim]\n")

    _pause()
    return True


def _round_or_back() -> bool:
    """One pass through the menu. Backing out of a question is not quitting."""
    try:
        return _one_round()
    except GoBack:
        console.print("[dim]Back to the menu.[/dim]\n")
        return True


def main() -> int:
    _banner()
    try:
        while _round_or_back():
            pass
    except Cancelled:
        console.print("\n[dim]Cancelled.[/dim]")
        return 130
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        return 130
    console.print("[dim]Bye.[/dim]")
    return 0
