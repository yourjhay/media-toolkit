"""Image operations. Pure functions: they take paths, they return results.

Nothing here prompts, prints, or knows a TUI exists, so the same functions
can back a flag-driven CLI later without changes.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pillow_heif
from PIL import Image, ImageOps

from .sizing import target_size

pillow_heif.register_heif_opener()

STRIP = "strip"
SAFE = "safe"
KEEP = "keep"
METADATA_MODES = (STRIP, SAFE, KEEP)

_GPS_IFD = 0x8825
_ORIENTATION = 274

OK = "ok"
SHORT = "short"
SKIPPED = "skipped"
FAILED = "failed"

_JPEG_ALIASES = {"jpg", "jpeg"}


@dataclass
class Result:
    """The outcome of one file's conversion."""

    source: Path
    output: Path | None
    status: str
    source_bytes: int = 0
    output_bytes: int = 0
    detail: str = ""
    # Encoder quality for JPEG/WebP; for a compressed PNG this is instead the
    # palette colour count, since PNG has no quality scale.
    quality: int | None = None
    achieved_pct: float | None = None

    @property
    def bytes_saved(self) -> int:
        """Bytes shrunk. A `short` run missed its target but still saved space."""
        if self.status not in (OK, SHORT):
            return 0
        return self.source_bytes - self.output_bytes


def _normalise_format(fmt: str) -> str:
    fmt = fmt.lower().lstrip(".")
    if fmt not in _JPEG_ALIASES | {"png"}:
        raise ValueError(f"Unsupported output format: {fmt!r}")
    return fmt


def _load_upright(path: Path) -> Image.Image:
    """Open an image with any EXIF rotation applied to the pixels.

    iPhone HEIC files are stored unrotated with the rotation recorded in EXIF.
    Anything that reads the file without honouring that tag shows it sideways,
    so the rotation is baked in here and the now-misleading tag dropped.
    """
    with Image.open(path) as img:
        img.load()
        upright = ImageOps.exif_transpose(img)
        # exif_transpose returns a new image with .format cleared; callers that
        # want to report what they opened need it kept.
        upright.format = img.format
        return upright


def check_metadata_mode(mode: str) -> str:
    """Reject an unknown mode up front.

    A bad mode is a caller's mistake, not one file's problem, so it raises
    rather than turning into a failed result for every image in the batch.
    """
    if mode not in METADATA_MODES:
        raise ValueError(f"metadata must be one of {METADATA_MODES}, got {mode!r}")
    return mode


def metadata_bytes(img: Image.Image, mode: str) -> bytes | None:
    """The EXIF block to write out, according to the chosen mode.

    `strip` writes none. `safe` keeps the camera, lens and date but drops the
    GPS coordinates, which is what makes a photo safe to publish. `keep` keeps
    the lot, including where it was taken.

    The orientation tag is removed in every mode: the rotation has already been
    applied to the pixels, so leaving the tag would rotate the image twice.
    """
    check_metadata_mode(mode)
    if mode == STRIP:
        return None

    raw = img.info.get("exif")
    if not raw:
        return None

    exif = Image.Exif()
    exif.load(raw)
    exif.pop(_ORIENTATION, None)
    if mode == SAFE:
        exif.pop(_GPS_IFD, None)
    return exif.tobytes() if len(exif) else None


def _save(
    img: Image.Image,
    out: Path,
    fmt: str,
    quality: int,
    metadata: str = SAFE,
) -> None:
    exif = metadata_bytes(img, metadata)
    extra = {"exif": exif} if exif else {}
    if fmt in _JPEG_ALIASES:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=quality, optimize=True, progressive=True, **extra)
    else:
        img.save(out, "PNG", optimize=True, **extra)


def convert_heic(
    src: Path,
    dest_dir: Path,
    fmt: str = "jpg",
    quality: int = 90,
    overwrite: bool = False,
    out_path: Path | None = None,
    metadata: str = SAFE,
) -> Result:
    """Convert one HEIC/HEIF file to JPEG or PNG.

    `out_path` overrides the derived name, which is how a batch keeps two
    same-named files from landing on top of each other.
    """
    src, dest_dir = Path(src), Path(dest_dir)
    fmt = _normalise_format(fmt)
    check_metadata_mode(metadata)
    out = Path(out_path) if out_path is not None else dest_dir / f"{src.stem}.{fmt}"
    src_bytes = src.stat().st_size

    if out.exists() and not overwrite:
        return Result(src, out, SKIPPED, src_bytes, out.stat().st_size, "output already exists")

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        img = _load_upright(src)
        _save(img, out, fmt, quality, metadata)
    except Exception as exc:
        return Result(src, None, FAILED, src_bytes, 0, f"{type(exc).__name__}: {exc}")

    return Result(src, out, OK, src_bytes, out.stat().st_size, quality=quality)


def convert_to_webp(
    src: Path,
    dest_dir: Path,
    quality: int = 80,
    lossless: bool = False,
    overwrite: bool = False,
    out_path: Path | None = None,
    metadata: str = SAFE,
) -> Result:
    """Convert one image to WebP, keeping any alpha channel."""
    src, dest_dir = Path(src), Path(dest_dir)
    check_metadata_mode(metadata)
    out = Path(out_path) if out_path is not None else dest_dir / f"{src.stem}.webp"
    src_bytes = src.stat().st_size

    if out.exists() and not overwrite:
        return Result(src, out, SKIPPED, src_bytes, out.stat().st_size, "output already exists")

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        img = _load_upright(src)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        exif = metadata_bytes(img, metadata)
        extra = {"exif": exif} if exif else {}
        img.save(out, "WEBP", quality=quality, lossless=lossless, method=6, **extra)
    except Exception as exc:
        return Result(src, None, FAILED, src_bytes, 0, f"{type(exc).__name__}: {exc}")

    return Result(src, out, OK, src_bytes, out.stat().st_size, quality=quality)


_MIN_JPEG_QUALITY = 20
_MAX_JPEG_QUALITY = 95
_PNG_COLOR_STEPS = (256, 128, 64, 32, 16, 8)


def _encode_jpeg(img: Image.Image, quality: int, exif: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    extra = {"exif": exif} if exif else {}
    img.save(buf, "JPEG", quality=quality, optimize=True, progressive=True, **extra)
    return buf.getvalue()


def _encode_png(img: Image.Image, colors: int | None, exif: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    if colors is not None:
        # FASTOCTREE is the one quantizer that handles an alpha channel,
        # so transparency survives the palette reduction.
        method = Image.Quantize.FASTOCTREE if img.mode == "RGBA" else Image.Quantize.MEDIANCUT
        img = img.quantize(colors=colors, method=method)
    extra = {"exif": exif} if exif else {}
    img.save(buf, "PNG", optimize=True, **extra)
    return buf.getvalue()


def _squeeze_jpeg(img: Image.Image, target_bytes: int, exif: bytes | None = None) -> tuple[bytes, int]:
    """Highest JPEG quality whose encoding fits in `target_bytes`.

    Binary search over the quality scale: ~7 encodes rather than 75.
    Falls back to the minimum quality when the target is out of reach.
    """
    best: tuple[bytes, int] | None = None
    low, high = _MIN_JPEG_QUALITY, _MAX_JPEG_QUALITY
    while low <= high:
        mid = (low + high) // 2
        data = _encode_jpeg(img, mid, exif)
        if len(data) <= target_bytes:
            best = (data, mid)
            low = mid + 1
        else:
            high = mid - 1
    return best if best is not None else (_encode_jpeg(img, _MIN_JPEG_QUALITY, exif), _MIN_JPEG_QUALITY)


def _squeeze_png(img: Image.Image, target_bytes: int, exif: bytes | None = None) -> tuple[bytes, int | None]:
    """Least aggressive palette reduction that fits, else the most aggressive.

    PNG is lossless and has no quality dial, so the only lever is colour count.
    """
    smallest: tuple[bytes, int | None] | None = None
    for colors in (None,) + _PNG_COLOR_STEPS:
        data = _encode_png(img, colors, exif)
        if len(data) <= target_bytes:
            return data, colors
        if smallest is None or len(data) < len(smallest[0]):
            smallest = (data, colors)
    return smallest  # type: ignore[return-value]


def compress(
    src: Path,
    dest_dir: Path,
    reduce_pct: float = 50,
    overwrite: bool = False,
    out_path: Path | None = None,
    metadata: str = SAFE,
) -> Result:
    """Re-encode one JPEG or PNG to be `reduce_pct` percent smaller on disk.

    The output keeps the source's format and pixel dimensions. When the target
    cannot be reached even at maximum compression the best attempt is still
    written, but the status is `short` and `achieved_pct` says how far it got —
    the caller is never told a target was met when it was not.
    """
    if not 0 < reduce_pct < 100:
        raise ValueError(f"reduce_pct must be between 1 and 99, got {reduce_pct}")
    check_metadata_mode(metadata)

    src, dest_dir = Path(src), Path(dest_dir)
    out = Path(out_path) if out_path is not None else dest_dir / src.name
    src_bytes = src.stat().st_size

    if out.resolve() == src.resolve():
        return Result(
            src, None, FAILED, src_bytes, 0,
            "refusing to compress a file over itself; choose a different output directory",
        )

    if out.exists() and not overwrite:
        return Result(src, out, SKIPPED, src_bytes, out.stat().st_size, "output already exists")

    target_bytes = int(src_bytes * (1 - reduce_pct / 100))

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        img = _load_upright(src)
        exif = metadata_bytes(img, metadata)
        suffix = src.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            data, quality = _squeeze_jpeg(img, target_bytes, exif)
        elif suffix == ".png":
            data, quality = _squeeze_png(img, target_bytes, exif)
        else:
            raise ValueError(f"compression supports .jpg and .png, not {suffix!r}")

        # Re-encoding can inflate an already-squeezed file. Never hand back
        # something bigger than what we were given.
        if len(data) >= src_bytes:
            data, quality = src.read_bytes(), None

        out.write_bytes(data)
    except Exception as exc:
        return Result(src, None, FAILED, src_bytes, 0, f"{type(exc).__name__}: {exc}")

    out_bytes = len(data)
    achieved = (1 - out_bytes / src_bytes) * 100 if src_bytes else 0.0
    if achieved + 1e-9 < reduce_pct:
        return Result(
            src, out, SHORT, src_bytes, out_bytes,
            f"could not reach {reduce_pct:g}% reduction; best was {achieved:.1f}%",
            quality=quality, achieved_pct=achieved,
        )
    return Result(src, out, OK, src_bytes, out_bytes, quality=quality, achieved_pct=achieved)


def _encode_webp(img: Image.Image, quality: int, exif: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    extra = {"exif": exif} if exif else {}
    img.save(buf, "WEBP", quality=quality, lossless=False, method=6, **extra)
    return buf.getvalue()


_PROBE_ENCODERS = {
    "jpg": _encode_jpeg,
    "jpeg": _encode_jpeg,
    "webp": _encode_webp,
}


def probe_quality_sizes(
    src: Path,
    fmt: str,
    qualities: Iterable[int],
    metadata: str = SAFE,
    resize_to: tuple[int, int] | None = None,
) -> dict[int, int]:
    """Encode `src` at each quality and report the byte count each produces.

    The source is decoded once and re-encoded per quality, using the same
    encoder settings the real conversion uses — an estimate produced by a
    different encoder would not predict anything.
    """
    fmt = fmt.lower().lstrip(".")
    try:
        encoder = _PROBE_ENCODERS[fmt]
    except KeyError:
        raise ValueError(f"Cannot probe sizes for format {fmt!r}") from None

    img = _load_upright(Path(src))
    if resize_to is not None and resize_to != img.size:
        img = img.resize(resize_to, Image.LANCZOS)
    exif = metadata_bytes(img, metadata)
    return {quality: len(encoder(img, quality, exif)) for quality in qualities}


def resize(
    src: Path,
    dest_dir: Path,
    max_width: int | None = None,
    max_height: int | None = None,
    percent: float | None = None,
    quality: int = 92,
    overwrite: bool = False,
    out_path: Path | None = None,
    metadata: str = SAFE,
) -> Result:
    """Scale one image down, keeping its format, name and aspect ratio.

    Quality defaults high, because downscaling has already discarded detail and
    there is no sense throwing away more in the same pass. Run the compressor
    afterwards to trade quality for size deliberately.
    """
    src, dest_dir = Path(src), Path(dest_dir)
    check_metadata_mode(metadata)
    out = Path(out_path) if out_path is not None else dest_dir / src.name
    src_bytes = src.stat().st_size

    if out.resolve() == src.resolve():
        return Result(
            src, None, FAILED, src_bytes, 0,
            "refusing to resize a file over itself; choose a different output directory",
        )

    if out.exists() and not overwrite:
        return Result(src, out, SKIPPED, src_bytes, out.stat().st_size, "output already exists")

    try:
        img = _load_upright(src)
        original = img.size
        target = target_size(original, max_width, max_height, percent)
    except ValueError:
        raise  # a contradictory instruction is the caller's bug, not this file's
    except Exception as exc:
        return Result(src, None, FAILED, src_bytes, 0, f"{type(exc).__name__}: {exc}")

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        if target != original:
            img = img.resize(target, Image.LANCZOS)
        _save(img, out, _normalise_format(src.suffix), quality, metadata)
    except Exception as exc:
        return Result(src, None, FAILED, src_bytes, 0, f"{type(exc).__name__}: {exc}")

    if target == original:
        detail = f"already within the target size ({original[0]}×{original[1]})"
    else:
        detail = f"{original[0]}×{original[1]} → {target[0]}×{target[1]}"

    return Result(src, out, OK, src_bytes, out.stat().st_size, detail, quality=quality)
