"""Validate a user-selected JPEG cover for in-memory book exports.

No cover artwork is read from a stored file, auto-imported from projects,
downloaded, or persisted by this module. JPEG bytes come only from an
explicitly selected browser file and are limited before decoding.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any, Dict

MAX_COVER_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_DIMENSION = 10_000

# Start-of-frame markers with an eight-bit height/width pair.
SOF = frozenset((0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF))


def _dimensions(jpeg: bytes):
    """Extract JPEG SOF dimensions using bounded marker traversal."""
    if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
        raise ValueError("Cover must be a complete JPEG image.")
    i = 2
    while i < len(jpeg) - 2:
        if jpeg[i] != 0xFF:
            raise ValueError("JPEG cover marker structure is invalid.")
        while i < len(jpeg) and jpeg[i] == 0xFF:
            i += 1
        if i >= len(jpeg):
            raise ValueError("Truncated JPEG marker.")
        marker = jpeg[i]
        i += 1
        if marker == 0xD9:
            break
        if marker in (0x01, *range(0xD0, 0xD8)):
            continue
        if marker == 0xDA:
            # Start of entropy coding. SOF must have preceded it.
            break
        if i + 2 > len(jpeg):
            raise ValueError("Truncated JPEG cover segment.")
        length = int.from_bytes(jpeg[i:i + 2], "big")
        if length < 2 or i + length > len(jpeg):
            raise ValueError("Invalid JPEG cover segment size.")
        if marker in SOF:
            if length < 8:
                raise ValueError("JPEG image header is incomplete.")
            precision = jpeg[i + 2]
            height = int.from_bytes(jpeg[i + 3:i + 5], "big")
            width = int.from_bytes(jpeg[i + 5:i + 7], "big")
            channels = jpeg[i + 7]
            if (precision != 8 or channels != 3 or width <= 0 or height <= 0
                    or width > MAX_DIMENSION or height > MAX_DIMENSION
                    or width * height > MAX_PIXELS):
                raise ValueError(
                    "Cover JPEG must be an 8-bit RGB image within 12 million pixels."
                )
            if max(width / height, height / width) > 6:
                raise ValueError("Cover dimensions are too extreme.")
            return width, height
        i += length
    raise ValueError("Could not find the cover JPEG image dimensions.")


def decode_cover(data: Any) -> Dict[str, Any] | None:
    if data in (None, ""):
        return None
    if not isinstance(data, str):
        raise ValueError("Cover must be a base64-encoded JPEG string.")
    if len(data) > 4 * ((MAX_COVER_BYTES + 2) // 3):
        raise ValueError("Cover exceeds the 2 MB JPEG size limit.")
    try:
        raw = base64.b64decode(data.encode("ascii"), validate=True)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Cover image is not valid base64 JPEG data.") from exc
    if not 100 <= len(raw) <= MAX_COVER_BYTES:
        raise ValueError("Cover JPEG must be 100 bytes to 2 MB.")
    width, height = _dimensions(raw)
    return {
        "jpeg": raw, "width": width, "height": height,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }
