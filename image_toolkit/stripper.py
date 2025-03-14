"""Removing metadata without touching the picture.

Every other operation decodes an image and encodes it again, which loses a
little quality every time. Metadata does not live in the pixels, so it can be
cut out of the container directly: the compressed image data is copied through
byte for byte and only the metadata blocks are dropped or rewritten.

Colour profiles are deliberately kept. They are metadata in the technical
sense but removing one visibly shifts the colours, which is not what anyone
means by "strip metadata".
"""

from __future__ import annotations

import zlib

from PIL import Image

STRIP_ALL = "all"
STRIP_LOCATION = "location"
MODES = (STRIP_ALL, STRIP_LOCATION)

_GPS_IFD = 0x8825

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class UnsupportedFormat(Exception):
    """The container is not one whose metadata blocks we know how to edit."""


def check_mode(mode: str) -> str:
    """Reject an unknown mode up front, before any file is touched."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    return mode


def _exif_without_location(raw: bytes) -> bytes | None:
    """The same EXIF block with the GPS section removed, or None if empty."""
    exif = Image.Exif()
    exif.load(raw)
    exif.pop(_GPS_IFD, None)
    return exif.tobytes() if len(exif) else None


# --- JPEG ------------------------------------------------------------------

_SOI = b"\xff\xd8"
_APP1 = 0xE1
_APP13 = 0xED
_COM = 0xFE
_SOS = 0xDA
_EXIF_HEADER = b"Exif\x00\x00"
_XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"


def _strip_jpeg(data: bytes, mode: str) -> bytes:
    if not data.startswith(_SOI):
        raise ValueError("not a JPEG file")

    out = bytearray(_SOI)
    position = 2

    while position < len(data) - 1:
        if data[position] != 0xFF:
            raise ValueError(f"malformed JPEG at byte {position}")
        marker = data[position + 1]

        if marker == _SOS:
            out += data[position:]  # scan data runs to the end, copied verbatim
            break

        length = int.from_bytes(data[position + 2 : position + 4], "big")
        end = position + 2 + length
        payload = data[position + 4 : end]

        if marker == _APP1 and payload.startswith(_EXIF_HEADER):
            if mode == STRIP_LOCATION:
                kept = _exif_without_location(payload)
                if kept:
                    body = _EXIF_HEADER + kept[len(_EXIF_HEADER):] if kept.startswith(
                        _EXIF_HEADER
                    ) else kept
                    out += bytes([0xFF, _APP1])
                    out += (len(body) + 2).to_bytes(2, "big")
                    out += body
            # STRIP_ALL, or an EXIF block that emptied out: drop the segment
        elif marker == _APP1 and payload.startswith(_XMP_HEADER):
            pass  # XMP can carry its own copy of the location; always dropped
        elif marker in (_APP13, _COM):
            pass  # IPTC/Photoshop resources and free-text comments
        else:
            out += data[position:end]  # JFIF, ICC profile, tables, frame headers

        position = end

    return bytes(out)


# --- PNG -------------------------------------------------------------------

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_METADATA_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"tIME"}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + zlib.crc32(kind + payload).to_bytes(4, "big")
    )


def _strip_png(data: bytes, mode: str) -> bytes:
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("not a PNG file")

    out = bytearray(_PNG_SIGNATURE)
    position = len(_PNG_SIGNATURE)

    while position < len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        end = position + 12 + length

        if kind == b"eXIf":
            if mode == STRIP_LOCATION:
                kept = _exif_without_location(payload)
                if kept:
                    out += _png_chunk(b"eXIf", kept)
        elif kind in _PNG_METADATA_CHUNKS:
            pass
        else:
            out += data[position:end]  # IHDR, PLTE, tRNS, iCCP, IDAT, IEND, …

        position = end
        if kind == b"IEND":
            break

    return bytes(out)


# --- WebP ------------------------------------------------------------------

_VP8X_EXIF_FLAG = 0x08
_VP8X_XMP_FLAG = 0x04
_WEBP_METADATA_CHUNKS = {b"EXIF", b"XMP "}


def _strip_webp(data: bytes, mode: str) -> bytes:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file")

    body = bytearray()
    position = 12

    while position < len(data):
        kind = data[position : position + 4]
        length = int.from_bytes(data[position + 4 : position + 8], "little")
        payload = data[position + 8 : position + 8 + length]
        end = position + 8 + length + (length % 2)  # chunks are even-aligned

        if kind == b"EXIF":
            if mode == STRIP_LOCATION:
                kept = _exif_without_location(payload)
                if kept:
                    body += _webp_chunk(b"EXIF", kept)
        elif kind in _WEBP_METADATA_CHUNKS:
            pass
        elif kind == b"VP8X":
            # The feature flags advertise which optional chunks exist. Leaving
            # them set after dropping the chunks makes the file self-contradictory.
            flags = payload[0] & ~_VP8X_XMP_FLAG
            if mode == STRIP_ALL:
                flags &= ~_VP8X_EXIF_FLAG
            body += _webp_chunk(b"VP8X", bytes([flags]) + payload[1:])
        else:
            body += data[position:end]

        position = end

    return b"RIFF" + (len(body) + 4).to_bytes(4, "little") + b"WEBP" + bytes(body)


def _webp_chunk(kind: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) % 2 else b""
    return kind + len(payload).to_bytes(4, "little") + payload + padding


# --- dispatch --------------------------------------------------------------

_STRIPPERS = {
    ".jpg": _strip_jpeg,
    ".jpeg": _strip_jpeg,
    ".png": _strip_png,
    ".webp": _strip_webp,
}


def strip_bytes(data: bytes, suffix: str, mode: str = STRIP_ALL) -> bytes:
    """Return `data` with its metadata removed, pixels untouched."""
    check_mode(mode)
    try:
        stripper = _STRIPPERS[suffix.lower()]
    except KeyError:
        raise UnsupportedFormat(
            f"cannot strip metadata from {suffix!r}; supported: "
            f"{', '.join(sorted(SUPPORTED_SUFFIXES))}"
        ) from None
    return stripper(data, mode)
