"""vidkit without the menu: one command, its answers given as arguments.

For scripts and AI agents, which have no terminal to answer prompts in. Each
command runs the same operation the menu does; only the asking is different.
Nothing is asked and nothing is remembered between runs, so the same command
always does the same thing.

`--json` puts a report on stdout that a program can read. The exit code says
how it went without reading anything: 0 worked, 1 something failed, 2 the
command itself was wrong.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from shared.format import human_bytes, human_duration

from .batch import find_videos, plan_batch, plan_mute_batch, run_batch
from .containers import playback_warning, supported_targets
from .download import download, ffmpeg_available, probe
from .formats import AUDIO, MP3, VIDEO, readable_formats
from .media import probe_media
from .operations import FAILED, OK, OVER, SKIPPED
from .tasks import compress_video, convert_video, mute_video, trim_video
from .timecode import parse_timecode
from .urls import clean_url

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

COMMANDS = ("info", "convert", "compress", "trim", "mute", "download", "audio", "formats")

NEEDS_FFMPEG = "This needs ffmpeg, which is not installed. Run  brew install ffmpeg  first."

# A bare number is megabytes, as it is in the menu.
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$", re.IGNORECASE)
_UNITS = {
    "": 1024 ** 2, "b": 1,
    "k": 1024, "kb": 1024,
    "m": 1024 ** 2, "mb": 1024 ** 2,
    "g": 1024 ** 3, "gb": 1024 ** 3,
}


def parse_size(text: str) -> int:
    """Bytes from "25MB", "25M", "1.5GB", "800KB" or a bare "25"."""
    match = _SIZE.match(text or "")
    unit = match.group(2).lower() if match else None
    if match is None or unit not in _UNITS:
        raise ValueError(f"Cannot read {text!r} as a size; try 25MB or 800KB")
    size = int(float(match.group(1)) * _UNITS[unit])
    if size <= 0:
        raise ValueError("A target size has to be more than nothing")
    return size


def parse_quality(text: str) -> int | None:
    """None for "best", otherwise the tallest picture wanted: "1080" or "1080p"."""
    value = (text or "").strip().lower()
    if value == "best":
        return None
    digits = value.removesuffix("p")
    if not digits.isdigit() or int(digits) == 0:
        raise ValueError(f"Cannot read {text!r} as a quality; try best, 1080 or 720")
    return int(digits)


class _Usage(Exception):
    """The command was wrong, as opposed to the work going wrong."""


class _Parser(argparse.ArgumentParser):
    # argparse prints and exits on a bad argument. Raising instead lets main()
    # return an exit code like every other outcome, so it can be tested.
    def error(self, message):
        raise _Usage(f"{self.prog}: {message}")


def _checked(parse):
    """An argparse type that reports the parser's own message, not a stock one."""
    def convert(text):
        try:
            return parse(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from None

    convert.__name__ = parse.__name__
    return convert


def _path(text: str) -> Path:
    # Absolute, so every path in a report still means something to a caller
    # that has since moved to another folder.
    return Path(text).expanduser().absolute()


def _existing(path: Path, command: str, folder_ok: bool) -> Path:
    if not path.exists():
        raise _Usage(f"vidkit {command}: no such file or folder: {path}")
    if path.is_dir() and not folder_ok:
        raise _Usage(f"vidkit {command}: takes one video file, not a folder: {path}")
    return path


def _link(text: str, command: str) -> str:
    try:
        return clean_url(text)
    except ValueError as exc:
        raise _Usage(f"vidkit {command}: {exc}") from None


class _Failed(Exception):
    """The work could not start at all, rather than failing for one file."""


def _require_ffmpeg() -> None:
    if not ffmpeg_available():
        raise _Failed(NEEDS_FFMPEG)


# --- reports ---------------------------------------------------------------

def _encode_row(result) -> dict:
    return {
        "source": str(result.source),
        "output": str(result.output) if result.output else None,
        "status": result.status,
        "detail": result.detail,
        "source_bytes": result.source_bytes,
        "output_bytes": result.output_bytes,
        "lossless": result.lossless,
    }


def _download_row(result) -> dict:
    return {
        "source": result.url,
        "output": str(result.path) if result.path else None,
        "status": result.status,
        "detail": result.detail,
        "title": result.title,
        "output_bytes": result.size_bytes,
    }


def _results(command: str, rows: list[dict]) -> dict:
    counts = {status: sum(1 for row in rows if row["status"] == status)
              for status in (OK, SKIPPED, FAILED, OVER)}
    return {"command": command, "ok": counts[FAILED] == 0, "counts": counts, "results": rows}


def _line(row: dict) -> str:
    status = row["status"].ljust(7)
    if row["status"] not in (OK, OVER):
        # A skip can still name a file, made by an earlier run.
        found = f": {row['output']}" if row["output"] else ""
        return f"{status} {row['source']}  {row['detail']}{found}"
    made = human_bytes(row["output_bytes"])
    if row.get("source_bytes"):
        made = f"{human_bytes(row['source_bytes'])} -> {made}"
    detail = f"  {row['detail']}" if row["detail"] else ""
    return f"{status} {row['source']} -> {row['output']}  ({made}){detail}"


def _print_results(report: dict) -> None:
    rows = report["results"]
    if not rows:
        print("No videos found.")
        return
    for row in rows:
        print(_line(row))
    if len(rows) > 1:
        counts = report["counts"]
        summary = f"{counts[OK]} ok, {counts[SKIPPED]} skipped, {counts[FAILED]} failed"
        if counts[OVER]:
            summary += f", {counts[OVER]} over target"
        print(summary)


def _print_info(report: dict) -> None:
    rows = [
        ("File", report["path"]),
        ("Size", human_bytes(report["size_bytes"])),
        ("Length", human_duration(report["duration"])),
        ("Picture", f"{report['width'] or '—'}x{report['height'] or '—'}  {report['video_codec'] or 'none'}"),
        ("Sound", report["audio_codec"] or "none"),
    ]
    for label, value in rows:
        print(f"{label:<8} {value}")


def _print_formats(report: dict) -> None:
    print(f"{'Title':<9} {report['title'] or '—'}")
    if report["uploader"]:
        print(f"{'From':<9} {report['uploader']}")
    print(f"{'Length':<9} {human_duration(report['duration'])}")
    if report["entries"] > 1:
        print(f"{'Playlist':<9} {report['entries']} videos")
    print()
    columns = ("id", "ext", "resolution", "fps", "size", "kind")
    widths = {c: max([len(c)] + [len(row[c]) for row in report["formats"]]) for c in columns}
    print("  ".join(c.upper().ljust(widths[c]) for c in columns))
    for row in report["formats"]:
        print("  ".join(row[c].ljust(widths[c]) for c in columns))


# --- the commands ----------------------------------------------------------

def _note(args, text: str) -> None:
    """What is starting, for a person watching. Kept off stdout and out of JSON."""
    if not args.json:
        print(text, file=sys.stderr)


def _default_out(source: Path) -> Path:
    return (source if source.is_dir() else source.parent) / "converted"


def _folder_rows(root: Path, dest: Path, recursive: bool, plan, run_one) -> list[dict]:
    """Every video in a folder, through one operation, as the menu does it."""
    infos = [probe_media(path) for path in find_videos(root, recursive, exclude=[dest])]
    items, settled = plan(infos)
    return [_encode_row(result) for result in run_batch(items, run_one) + settled]


def _info(args) -> dict:
    path = _existing(args.path, "info", folder_ok=False)
    _require_ffmpeg()
    info = probe_media(path)
    if info.error:
        raise _Failed(info.error)
    report = {"command": "info", "ok": True, **asdict(info)}
    report["path"] = str(info.path)
    del report["error"]
    return report


def _convert(args) -> dict:
    source = _existing(args.path, "convert", folder_ok=True)
    _require_ffmpeg()
    dest = args.out or _default_out(source)
    target = args.to

    if source.is_dir():
        def convert_one(item, report):
            return convert_video(item.info.path, item.dest_dir, target,
                                 force_video_encode=item.force_video_encode,
                                 probe=lambda _path: item.info)

        _note(args, f"Converting the videos in {source} to {target}…")
        rows = _folder_rows(
            source, dest, args.recursive,
            lambda infos: plan_batch(infos, source, dest, target,
                                     force_awkward=not args.keep_codec),
            convert_one,
        )
        return _results("convert", rows)

    info = probe_media(source)
    force = (not args.keep_codec and not info.error
             and playback_warning(info.video_codec, target) is not None)
    _note(args, f"Converting {source.name} to {target}…")
    result = convert_video(source, dest, target, overwrite=args.overwrite,
                           force_video_encode=force, probe=lambda _path: info)
    return _results("convert", [_encode_row(result)])


def _compress(args) -> dict:
    source = _existing(args.path, "compress", folder_ok=False)
    _require_ffmpeg()
    _note(args, f"Compressing {source.name} to {human_bytes(args.size)}…")
    result = compress_video(source, args.out or _default_out(source),
                            target_bytes=args.size, overwrite=args.overwrite)
    return _results("compress", [_encode_row(result)])


def _trim(args) -> dict:
    source = _existing(args.path, "trim", folder_ok=False)
    _require_ffmpeg()
    _note(args, f"Trimming {source.name}…")
    result = trim_video(source, args.out or _default_out(source),
                        start=args.start, end=args.end, precise=args.exact,
                        overwrite=args.overwrite)
    return _results("trim", [_encode_row(result)])


def _mute(args) -> dict:
    source = _existing(args.path, "mute", folder_ok=True)
    _require_ffmpeg()
    dest = args.out or _default_out(source)

    if source.is_dir():
        def mute_one(item, report):
            return mute_video(item.info.path, item.dest_dir, probe=lambda _path: item.info)

        _note(args, f"Muting the videos in {source}…")
        rows = _folder_rows(source, dest, args.recursive,
                            lambda infos: plan_mute_batch(infos, source, dest), mute_one)
        return _results("mute", rows)

    _note(args, f"Muting {source.name}…")
    result = mute_video(source, dest, overwrite=args.overwrite)
    return _results("mute", [_encode_row(result)])


def _download(args) -> dict:
    url = _link(args.url, "download")
    _note(args, "Downloading…")
    result = download(url, args.out or Path.cwd(), mode=VIDEO,
                      max_height=args.quality, ffmpeg=ffmpeg_available())
    return _results("download", [_download_row(result)])


def _audio(args) -> dict:
    url = _link(args.url, "audio")
    ffmpeg = ffmpeg_available()
    convert_to = MP3 if args.mp3 and ffmpeg else None
    if args.mp3 and not ffmpeg:
        print("ffmpeg is not installed, so the audio is kept in the format the site serves.",
              file=sys.stderr)
    _note(args, "Downloading the audio…")
    result = download(url, args.out or Path.cwd(), mode=AUDIO, ffmpeg=ffmpeg,
                      convert_to=convert_to, keep_original=args.keep_original)
    return _results("audio", [_download_row(result)])


def _formats(args) -> dict:
    url = _link(args.url, "formats")
    info = probe(url)
    if info.error:
        raise _Failed(info.error)
    return {
        "command": "formats", "ok": True, "url": url,
        "title": info.title, "uploader": info.uploader, "duration": info.duration,
        "entries": info.entries,
        "formats": readable_formats({"formats": info.formats or []}),
    }


# --- the parser ------------------------------------------------------------

_DESCRIPTION = """\
Video tools without the menu, for scripts and AI agents.
Run vidkit with no arguments, in a terminal, for the interactive menu."""

_EPILOG = """\
Every command takes --json, before or after the command name, and then
prints one JSON object on stdout. Progress notes and errors go to stderr.

Exit codes:  0 it worked (skipped files count as worked)
             1 something failed; the report says what
             2 the command itself was wrong; nothing was done

Nothing is ever written over a source file. Output goes to a "converted"
folder beside the source unless --out says otherwise.

Full guide: docs/agents.md in the toolkit's folder."""


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS on both levels, or the command's default would overwrite a
    # --json given before the command name.
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print a JSON report on stdout instead of text")

    writes = argparse.ArgumentParser(add_help=False)
    writes.add_argument("--out", type=_path, metavar="DIR",
                        help="folder to save into (default: 'converted' beside the source)")
    writes.add_argument("--overwrite", action="store_true",
                        help="replace an earlier output of the same name; folders always skip them")

    folders = argparse.ArgumentParser(add_help=False)
    folders.add_argument("-r", "--recursive", action="store_true",
                         help="given a folder, include its subfolders, mirrored into the output")

    fetches = argparse.ArgumentParser(add_help=False)
    fetches.add_argument("url", help="the link, e.g. a YouTube, TikTok or Vimeo page")
    fetches.add_argument("--out", type=_path, metavar="DIR",
                         help="folder to save into (default: the current folder)")

    parser = _Parser(prog="vidkit", description=_DESCRIPTION, epilog=_EPILOG,
                     formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common])
    commands = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    def command(name, help_, parents=(), run=None):
        sub = commands.add_parser(name, help=help_, description=help_,
                                  parents=[common, *parents])
        sub.set_defaults(run=run)
        return sub

    info = command("info", "describe a local video: length, size, picture and sound", run=_info)
    info.add_argument("path", type=_path, help="a video file")

    convert = command("convert", "change the container; copies the streams when it can",
                      (writes, folders), _convert)
    convert.add_argument("path", type=_path, help="a video file, or a folder of them")
    convert.add_argument("--to", required=True, choices=supported_targets(),
                         help="the format to convert to")
    convert.add_argument("--keep-codec", action="store_true",
                         help="copy AV1/VP9 into mp4/mov as-is instead of re-encoding to H.264; "
                              "lossless and fast, but QuickTime and Photos will not open it")

    compress = command("compress", "re-encode one video to land near a target size",
                       (writes,), _compress)
    compress.add_argument("path", type=_path, help="a video file")
    compress.add_argument("--size", required=True, type=_checked(parse_size),
                          help="target size: 25MB, 800KB, 1.5GB; a bare number is MB")

    trim = command("trim", "keep only part of a video", (writes,), _trim)
    trim.add_argument("path", type=_path, help="a video file")
    trim.add_argument("--start", default=0.0, type=_checked(parse_timecode),
                      help="where to begin: 90, 1:30 or 1:02:03 (default: the beginning)")
    trim.add_argument("--end", type=_checked(parse_timecode),
                      help="where to stop (default: the end)")
    trim.add_argument("--exact", action="store_true",
                      help="cut exactly, re-encoding; otherwise the cut is instant but "
                           "starts at the nearest keyframe")

    mute = command("mute", "take the sound out; the picture is copied untouched",
                   (writes, folders), _mute)
    mute.add_argument("path", type=_path, help="a video file, or a folder of them")

    fetch = command("download", "download a video from a link", (fetches,), _download)
    fetch.add_argument("--quality", default=None, type=_checked(parse_quality),
                       help="best (default), or the tallest picture wanted: 2160, 1080, 720…")

    audio = command("audio", "download only the audio from a link", (fetches,), _audio)
    audio.add_argument("--mp3", action=argparse.BooleanOptionalAction, default=True,
                       help="convert to MP3 (default); --no-mp3 keeps what the site serves")
    audio.add_argument("--keep-original", action="store_true",
                       help="keep the downloaded file as well as the MP3")

    formats = command("formats", "list what a link offers, without downloading", run=_formats)
    formats.add_argument("url", help="the link")

    return parser


def _usage(exc: _Usage) -> int:
    print(exc, file=sys.stderr)
    print("Run  vidkit --help  or  vidkit <command> --help  for the options.", file=sys.stderr)
    return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except _Usage as exc:
        return _usage(exc)
    except SystemExit as exc:      # --help, which argparse ends by exiting
        return exc.code if isinstance(exc.code, int) else EXIT_OK

    if args.command is None:
        print("vidkit's menu needs a terminal. Without one, give it a command:\n",
              file=sys.stderr)
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    args.json = getattr(args, "json", False)
    try:
        report = args.run(args)
    except _Usage as exc:
        return _usage(exc)
    except _Failed as exc:
        report = {"command": args.command, "ok": False, "error": str(exc)}

    if args.json:
        print(json.dumps(report, indent=2))
    elif "error" in report:
        print(f"vidkit {args.command}: {report['error']}", file=sys.stderr)
    elif "results" in report:
        _print_results(report)
    elif args.command == "info":
        _print_info(report)
    else:
        _print_formats(report)

    return EXIT_OK if report["ok"] else EXIT_FAILED
