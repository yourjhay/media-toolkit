"""Reading what a picture says about itself.

Read-only: nothing here writes a file. The extraction is pure enough to test,
so the fiddly parts — GPS rationals, hemisphere signs, missing blocks — are
settled here rather than on someone's photos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .core import _load_upright

# EXIF tag numbers, named so the extraction table below reads as prose.
_MAKE = 0x010F
_MODEL = 0x0110
_SOFTWARE = 0x0131
_DATETIME = 0x0132
_ARTIST = 0x013B
_COPYRIGHT = 0x8298
_EXPOSURE = 0x829A
_FNUMBER = 0x829D
_ISO = 0x8827
_DATETIME_ORIGINAL = 0x9003
_FOCAL_LENGTH = 0x920A
_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_LENS_MODEL = 0xA434
_BODY_SERIAL = 0xA431


@dataclass
class MetadataField:
    label: str
    value: str
    sensitive: bool = False


@dataclass
class FileMetadata:
    path: Path
    name: str
    size_bytes: int
    dimensions: tuple[int, int] | None = None
    format: str | None = None
    mode: str | None = None
    tag_count: int = 0
    fields: list[MetadataField] = field(default_factory=list)
    coordinates: tuple[float, float] | None = None
    error: str | None = None

    @property
    def has_location(self) -> bool:
        return self.coordinates is not None


def _to_float(value) -> float:
    """EXIF rationals arrive as IFDRational, tuple or plain number."""
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        return float(numerator) / float(denominator or 1)
    return float(value)


def decode_coordinates(gps: dict) -> tuple[float, float] | None:
    """Decimal latitude and longitude from a GPS IFD, or None.

    The degrees/minutes/seconds triples are always positive; the hemisphere
    letters are the only thing carrying the sign.
    """
    try:
        lat_ref, lat = gps[1], gps[2]
        lon_ref, lon = gps[3], gps[4]
        latitude = sum(_to_float(part) / 60**i for i, part in enumerate(lat))
        longitude = sum(_to_float(part) / 60**i for i, part in enumerate(lon))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None

    if str(lat_ref).upper().startswith("S"):
        latitude = -latitude
    if str(lon_ref).upper().startswith("W"):
        longitude = -longitude
    return latitude, longitude


def _dms(value: float, positive: str, negative: str) -> str:
    letter = positive if value >= 0 else negative
    value = abs(value)
    degrees = int(value)
    minutes_full = (value - degrees) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60)
    if seconds == 60:
        seconds, minutes = 0, minutes + 1
    if minutes == 60:
        minutes, degrees = 0, degrees + 1
    return f"{degrees}°{minutes:02d}'{seconds:02d}\"{letter}"


def format_coordinates(latitude: float, longitude: float) -> str:
    return f"{_dms(latitude, 'N', 'S')}, {_dms(longitude, 'E', 'W')}"


def maps_link(latitude: float, longitude: float) -> str:
    """Six decimal places is roughly 10cm; the raw float is digits of noise."""
    return f"https://www.google.com/maps?q={round(latitude, 6)},{round(longitude, 6)}"


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).strip().strip("\x00")


def _camera(exif) -> str:
    make, model = _clean(exif.get(_MAKE)), _clean(exif.get(_MODEL))
    if make and model.lower().startswith(make.lower()):
        return model
    return " ".join(part for part in (make, model) if part)


def _exposure(detail) -> str:
    parts = []
    if (shutter := detail.get(_EXPOSURE)) is not None:
        seconds = _to_float(shutter)
        parts.append(f"1/{round(1 / seconds)}s" if 0 < seconds < 1 else f"{seconds:g}s")
    if (aperture := detail.get(_FNUMBER)) is not None:
        parts.append(f"f/{_to_float(aperture):g}")
    if (iso := detail.get(_ISO)) is not None:
        parts.append(f"ISO {iso}")
    if (focal := detail.get(_FOCAL_LENGTH)) is not None:
        parts.append(f"{_to_float(focal):g}mm")
    return "   ".join(parts)


def read_metadata(path: Path) -> FileMetadata:
    """Everything worth showing about one image file."""
    path = Path(path)
    data = FileMetadata(path=path, name=path.name, size_bytes=path.stat().st_size)

    try:
        img = _load_upright(path)
    except Exception as exc:
        data.error = f"{type(exc).__name__}: {exc}"
        return data

    data.dimensions = img.size
    data.format = img.format
    data.mode = img.mode

    exif = img.getexif()
    data.tag_count = len(exif)
    detail = exif.get_ifd(_EXIF_IFD) or {}
    gps = exif.get_ifd(_GPS_IFD) or {}

    candidates: list[tuple[str, str, bool]] = [
        ("Camera", _camera(exif), False),
        ("Lens", _clean(detail.get(_LENS_MODEL)), False),
        ("Exposure", _exposure(detail), False),
        ("Taken", _clean(detail.get(_DATETIME_ORIGINAL)) or _clean(exif.get(_DATETIME)), False),
        ("Software", _clean(exif.get(_SOFTWARE)), False),
        ("Artist", _clean(exif.get(_ARTIST)), False),
        ("Copyright", _clean(exif.get(_COPYRIGHT)), False),
        ("Serial number", _clean(detail.get(_BODY_SERIAL)), True),
    ]

    coordinates = decode_coordinates(gps)
    if coordinates is not None:
        data.coordinates = coordinates
        candidates.append(("Location", format_coordinates(*coordinates), True))

    data.fields = [
        MetadataField(label, value, sensitive)
        for label, value, sensitive in candidates
        if value.strip()
    ]
    return data


def pretty_datetime(raw: str) -> str:
    """Turn EXIF's "2026:09:21 14:00:00" into "2026-09-21 14:00".

    EXIF separates the date parts with colons, which reads as a time to
    everyone who is not a camera. Anything unrecognised is left alone.
    """
    if not raw:
        return raw
    date, _, time = raw.partition(" ")
    parts = date.split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return raw
    clock = ":".join(time.split(":")[:2]) if time else ""
    return f"{parts[0]}-{parts[1]}-{parts[2]}" + (f" {clock}" if clock else "")
