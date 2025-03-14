"""The interactive terminal menu.

This layer only asks questions and draws results. Every decision it collects
is handed to `planning`, and every byte of image work happens in `core`.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from .core import FAILED, KEEP, OK, SAFE, SHORT, SKIPPED, STRIP, probe_quality_sizes
from .discovery import find_images
from .estimate import QUALITY_ANCHORS, build_quality_model, compress_target
from .info import FileInfo, FolderInfo, inspect_source
from .metadata import FileMetadata, maps_link, pretty_datetime, read_metadata
from .sizing import target_size
from shared.chrome import choose_from_cards, print_banner
from shared.format import human_bytes, size_change_row
from shared.prompts import STYLE, Cancelled, ask as _ask, ask_int as _ask_int
from shared.prompts import ask_path as _shared_ask_path, pause as _pause
from .stripper import STRIP_ALL, STRIP_LOCATION
from .jobs import Summary, run_batch
from .planning import (
    BACK,
    OPERATIONS,
    asks_metadata,
    QUIT,
    READ_ONLY,
    assign_output_paths,
    default_output_dir,
    extensions_for,
    format_estimate,
    make_operation,
    median_by_size,
    menu_items,
    output_name,
)

console = Console()


_STATUS_LABEL = {
    OK: ("[green]done[/green]", "green"),
    SHORT: ("[yellow]short of target[/yellow]", "yellow"),
    SKIPPED: ("[dim]skipped[/dim]", "dim"),
    FAILED: ("[red]failed[/red]", "red"),
}











TITLE = "IMG TOOLKIT"
SUBTITLE = "HEIC → JPG/PNG   ·   resize   ·   compress   ·   metadata"


def _banner() -> None:
    print_banner(console, TITLE, SUBTITLE)


def _choose_operation() -> str:
    chosen = choose_from_cards(console, menu_items(), "What would you like to do?")
    picked = next(item for item in menu_items() if item.key == chosen)
    console.print(f"[#00b894]?[/#00b894] [bold]Operation:[/bold] [#0984e3]{picked.title}[/#0984e3]")
    return chosen


def _ask_path(message: str, default: str | None = None) -> Path:
    return _shared_ask_path(console, message, default)


def _choose_source() -> Path:
    while True:
        source = _ask_path("Source file or folder:")
        if source.exists():
            return source
        console.print(f"[red]No such path:[/red] {source}")


ACCENT = "#ff8fa3"


def _field_of(data: FileMetadata, label: str) -> str:
    for item in data.fields:
        if item.label == label:
            return item.value
    return ""


def _metadata_detail(data: FileMetadata) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Size", human_bytes(data.size_bytes))
    if data.dimensions:
        width, height = data.dimensions
        table.add_row("Image", f"{width} × {height}   {data.format}   {data.mode}")
    if data.error:
        table.add_row("Problem", f"[red]{data.error}[/red]")

    if data.fields:
        table.add_row("", "")
        for item in data.fields:
            value = pretty_datetime(item.value) if item.label == "Taken" else item.value
            if item.sensitive:
                table.add_row(f"[{ACCENT}]{item.label}[/{ACCENT}]", f"[{ACCENT}]{value}[/{ACCENT}]")
            else:
                table.add_row(item.label, value)
    elif not data.error:
        table.add_row("Metadata", "[dim]none recorded[/dim]")

    console.print(Panel(table, title=data.name, border_style=ACCENT, title_align="left"))

    if data.has_location:
        link = maps_link(*data.coordinates)
        console.print(f"  [{ACCENT}]This photo records where it was taken.[/{ACCENT}]")
        # A terminal hyperlink: clicking opens the map where the terminal
        # supports it, and reads as a plain URL where it does not.
        console.print(f"  [dim][link={link}]{link}[/link][/dim]")
        console.print(
            "  [dim]Pick “Strip everything” under Photo metadata when converting, "
            "before sharing it.[/dim]"
        )
    console.print()


def _metadata_summary(readings: list[FileMetadata]) -> None:
    table = Table(box=box.SIMPLE, header_style="bold", padding=(0, 1))
    table.add_column("File")
    table.add_column("Size", justify="right")
    table.add_column("Pixels", justify="right")
    table.add_column("Camera")
    table.add_column("Taken")
    table.add_column("Location")

    for data in readings:
        size = f"{data.dimensions[0]}×{data.dimensions[1]}" if data.dimensions else "—"
        table.add_row(
            data.name,
            human_bytes(data.size_bytes),
            size,
            _field_of(data, "Camera") or "[dim]—[/dim]",
            pretty_datetime(_field_of(data, "Taken")) or "[dim]—[/dim]",
            f"[{ACCENT}]yes[/{ACCENT}]" if data.has_location else "[dim]no[/dim]",
        )
    console.print(table)

    located = [d for d in readings if d.has_location]
    if located:
        console.print(
            f"  [{ACCENT}]{len(located)} of {len(readings)} record where they were "
            f"taken.[/{ACCENT}]"
        )
    else:
        console.print("  [dim]None of these record a location.[/dim]")
    console.print()


def _detail_choices(readings: list[FileMetadata]) -> list[Choice]:
    """One entry per file, then a way out.

    The exit entry carries a sentinel rather than None: questionary swaps a
    None value for the label text, which would arrive here as a string where
    an index was expected.
    """
    choices = [Choice(data.name, index) for index, data in enumerate(readings)]
    choices.append(Choice("Back to the menu", BACK))
    return choices


def _show_metadata(files: list[Path]) -> None:
    if len(files) == 1:
        _metadata_detail(read_metadata(files[0]))
        return

    with console.status(f"[dim]Reading {len(files)} files…[/dim]", spinner="dots"):
        readings = [read_metadata(path) for path in files]
    _metadata_summary(readings)

    while True:
        picked = _ask(
            questionary.select(
                "Look at one in detail?", choices=_detail_choices(readings), style=STYLE
            )
        )
        if picked == BACK:
            return
        _metadata_detail(readings[picked])


def _source_panel(info: FileInfo | FolderInfo) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 2))
    if isinstance(info, FileInfo):
        table.add_row("File", f"[bold]{info.name}[/bold]")
        table.add_row("Size", human_bytes(info.size_bytes))
        if info.dimensions:
            width, height = info.dimensions
            table.add_row("Image", f"{width} × {height}   {info.format}")
        if info.error:
            table.add_row("Problem", f"[red]{info.error}[/red]")
        table.add_row("Location", str(info.location))
        title = "Source file"
    else:
        table.add_row("Folder", f"[bold]{info.name}[/bold]")
        table.add_row("Location", str(info.location))
        if info.total_count:
            table.add_row("Here", f"{info.here_count} images, {human_bytes(info.here_bytes)}")
            if info.nested_count:
                table.add_row(
                    "Subfolders",
                    f"{info.nested_count} images, {human_bytes(info.nested_bytes)}",
                )
        else:
            table.add_row("Contents", "[yellow]no matching images[/yellow]")
        title = "Source folder"
    return Panel(table, title=title, border_style="cyan", title_align="left")


def _quality_describer(files: list[Path], probe_format: str):
    """Measure one real file, so typing a quality can show a live size.

    Returns None when there is nothing to measure, in which case the prompt
    simply has no hint.
    """
    sample = median_by_size(files)
    if sample is None:
        return None

    total = sum(f.stat().st_size for f in files)
    with console.status(f"[dim]Sampling {sample.name}…[/dim]", spinner="dots"):
        try:
            measured = probe_quality_sizes(sample, probe_format, QUALITY_ANCHORS)
        except Exception as exc:
            console.print(f"[yellow]Could not measure sizes ({exc}); continuing without estimates.[/yellow]")
            return None

    model = build_quality_model(
        lambda q: measured[q],
        source_bytes=sample.stat().st_size,
        anchors=QUALITY_ANCHORS,
        batch_source_bytes=total,
        sample_name=sample.name,
    )
    if model.scaled:
        console.print(
            f"[dim]Estimates extrapolated from {sample.name}, "
            f"the median of {len(files)} files.[/dim]"
        )
    return lambda quality: format_estimate(model.estimate(quality), model.source_bytes)


def _ask_metadata() -> str:
    """How much of the camera's own record to carry into the output."""
    return _ask(
        questionary.select(
            "Photo metadata:",
            choices=[
                Choice("Keep camera and date, drop location", SAFE),
                Choice("Strip everything  —  safest to share", STRIP),
                Choice("Keep everything, including location", KEEP),
            ],
            style=STYLE,
        )
    )


def _resize_estimate(files: list[Path], options: dict) -> str | None:
    """One probe at the chosen dimensions, scaled to the batch.

    Only JPEG sources are measured; PNG is lossless and its size after a resize
    depends on the picture in ways a single sample would misrepresent.
    """
    sample = median_by_size(files)
    if sample is None or sample.suffix.lower() not in (".jpg", ".jpeg"):
        return None

    info = inspect_source(sample, set())
    if not isinstance(info, FileInfo) or not info.dimensions:
        return None

    spec = {k: v for k, v in options.items() if k in ("max_width", "max_height", "percent")}
    total = sum(f.stat().st_size for f in files)
    try:
        target = target_size(info.dimensions, **spec)
        with console.status(f"[dim]Measuring {sample.name}…[/dim]", spinner="dots"):
            measured = probe_quality_sizes(
                sample, "jpg", (RESIZE_QUALITY,),
                metadata=options.get("metadata", SAFE), resize_to=target,
            )
    except Exception:
        return None

    scaled = round(measured[RESIZE_QUALITY] * total / sample.stat().st_size)
    return f"{format_estimate(scaled, total)}   [{target[0]} × {target[1]}]"


RESIZE_QUALITY = 92

RESIZE_PRESETS = (
    ("Fit within 1920 × 1920", "large screens and web", 1920),
    ("Fit within 1200 × 1200", "email and documents", 1200),
    ("Fit within 800 × 800", "thumbnails and previews", 800),
)


def _collect_resize_options() -> dict:
    choices = [
        Choice(f"{label}   —   {why}", ("box", size)) for label, why, size in RESIZE_PRESETS
    ]
    choices.append(Choice("Percentage of the original", ("percent", None)))
    choices.append(Choice("Custom maximum width and height", ("custom", None)))

    kind, size = _ask(questionary.select("Resize to:", choices=choices, style=STYLE))

    if kind == "box":
        return {"max_width": size, "max_height": size}
    if kind == "percent":
        return {"percent": _ask_int("Scale to what percent of the original? (1-100):", 50, 1, 100)}
    return {
        "max_width": _ask_int("Maximum width in pixels:", 1920, 1, 20000),
        "max_height": _ask_int("Maximum height in pixels:", 1920, 1, 20000),
    }


def _collect_strip_options() -> dict:
    return {
        "mode": _ask(
            questionary.select(
                "Remove:",
                choices=[
                    Choice("Everything  —  camera, date, location, comments", STRIP_ALL),
                    Choice("Location only  —  keep the camera and date", STRIP_LOCATION),
                ],
                style=STYLE,
            )
        )
    }


def _collect_options(operation: str, files: list[Path]) -> dict:
    if operation == "resize":
        return _collect_resize_options()

    if operation == "strip":
        return _collect_strip_options()

    if operation == "heic":
        fmt = _ask(
            questionary.select(
                "Convert to:",
                choices=[Choice("JPG", "jpg"), Choice("PNG", "png")],
                style=STYLE,
            )
        )
        options = {"fmt": fmt}
        if fmt == "jpg":
            options["quality"] = _ask_int(
                "JPEG quality (1-100):", 90, 1, 100, _quality_describer(files, "jpg")
            )
        return options

    if operation == "webp":
        lossless = _ask(
            questionary.confirm("Lossless WebP? (larger files, exact pixels)", default=False, style=STYLE)
        )
        options = {"lossless": lossless}
        if not lossless:
            options["quality"] = _ask_int(
                "WebP quality (1-100):", 80, 1, 100, _quality_describer(files, "webp")
            )
        return options

    total = sum(f.stat().st_size for f in files)

    def describe(pct: int) -> str:
        return format_estimate(compress_target(total, pct), total)

    return {
        "reduce_pct": _ask_int(
            "Shrink files by what percent? (1-99):", 50, 1, 99, describe
        )
    }


def _preview(
    files: list[Path],
    dest_dir: Path,
    operation: str,
    options: dict,
    renamed: list[tuple[Path, Path]],
    estimate: str | None = None,
) -> None:
    total = sum(f.stat().st_size for f in files)
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Files", str(len(files)))
    table.add_row("Total size", human_bytes(total))
    table.add_row("Output", str(dest_dir))
    for key, value in options.items():
        table.add_row(key.replace("_", " ").capitalize(), str(value))
    if estimate:
        table.add_row("Estimated output", estimate)
    if renamed:
        table.add_row("Renamed", f"[yellow]{len(renamed)}[/yellow] (same name in another folder)")
    console.print(Panel(table, title=OPERATIONS[operation], border_style="cyan"))

    for src, out in renamed[:5]:
        console.print(f"[dim]  {src.name} from {src.parent.name}/ → {out.name}[/dim]")
    if len(renamed) > 5:
        console.print(f"[dim]  …and {len(renamed) - 5} more[/dim]")


def _run(files: list[Path], operation) -> Summary:
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Working", total=len(files))

        def advance(result) -> None:
            progress.update(task, advance=1, description=result.source.name[:34])

        summary = run_batch(files, operation, on_progress=advance)
        progress.update(task, description="Done")
    return summary


def _report(summary: Summary, dest_dir: Path | None = None) -> None:
    counts = summary.counts
    table = Table(box=None, padding=(0, 2))
    table.add_column("Outcome")
    table.add_column("Files", justify="right")
    for status in (OK, SHORT, SKIPPED, FAILED):
        if counts.get(status):
            table.add_row(_STATUS_LABEL[status][0], str(counts[status]))
    label, value = size_change_row(summary.bytes_saved)
    table.add_row(f"[bold]{label}[/bold]", f"[bold]{value}[/bold]")
    console.print(table)

    written = summary.written
    if written and dest_dir is not None:
        console.print()
        noun = "file" if len(written) == 1 else "files"
        console.print(f"  Saved {len(written)} {noun} to")
        console.print(f"  [bold]{dest_dir}[/bold]")

    # Every non-success gets its reason spelled out. A bare "skipped 1" leaves
    # the user with no idea why nothing happened.
    skipped = summary.of_status(SKIPPED)
    for result in skipped:
        console.print(f"  [dim]·[/dim] {result.source.name}: {result.detail}")
    if skipped:
        console.print(
            "  [dim]Nothing was overwritten. Answer yes to “Overwrite files already "
            "in the output folder?”, or pick an empty output folder.[/dim]"
        )
    for result in summary.of_status(SHORT):
        console.print(f"  [yellow]·[/yellow] {result.source.name}: {result.detail}")
    for result in summary.of_status(FAILED):
        console.print(f"  [red]·[/red] {result.source.name}: {result.detail}")


def _one_round() -> bool:
    """Run a single operation end to end. Returns False when the user quits."""
    operation = _choose_operation()
    if operation == QUIT:
        return False

    source = _choose_source()
    extensions = extensions_for(operation)
    console.print(_source_panel(inspect_source(source, extensions)))

    recursive = False
    if source.is_dir():
        recursive = _ask(questionary.confirm("Include subfolders?", default=False, style=STYLE))

    if operation in READ_ONLY:
        files = find_images(source, extensions, recursive=recursive)
        if not files:
            console.print("[yellow]No matching images found there.[/yellow]\n")
            return True
        _show_metadata(files)
        return True

    dest_dir = _ask_path("Output folder:", default=str(default_output_dir(source)))

    # Discovered before the options are asked, so a quality prompt can measure
    # a real file, and so an empty run is caught before asking anything else.
    files = find_images(source, extensions, recursive=recursive, exclude=[dest_dir])
    if not files:
        console.print("[yellow]No matching images found there.[/yellow]\n")
        return True

    options = _collect_options(operation, files)
    if asks_metadata(operation):
        options["metadata"] = _ask_metadata()
    estimate = _resize_estimate(files, options) if operation == "resize" else None
    options["overwrite"] = _ask(
        questionary.confirm("Overwrite files already in the output folder?", default=False, style=STYLE)
    )

    # A recursive run flattens subfolders, so two same-named photos would
    # otherwise land on the same output file.
    def name_of(src: Path) -> str:
        return output_name(operation, src, options.get("fmt"))

    outputs = assign_output_paths(files, dest_dir, name_of)
    renamed = [(src, out) for src, out in outputs.items() if out.name != name_of(src)]

    _preview(files, dest_dir, operation, options, renamed, estimate)
    if not _ask(questionary.confirm(f"Process {len(files)} file(s)?", default=True, style=STYLE)):
        console.print("[dim]Cancelled.[/dim]\n")
        return True

    summary = _run(files, make_operation(operation, dest_dir, outputs=outputs, **options))
    _report(summary, dest_dir)
    console.print()
    # The menu is twenty lines tall and redraws immediately; without this the
    # summary scrolls away before it can be read.
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
