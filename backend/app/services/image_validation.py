"""Untrusted image checks: sniff real format from bytes, read dimensions, enforce limits.

The declared Content-Type is never trusted alone. Bytes stay in memory and are
never written to the database or logs.
"""

import os
import struct
from dataclasses import dataclass

from fastapi import HTTPException

ALLOWED_DECLARED = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream", ""}
MIN_SIDE_PX = 100
MAX_SIDE_PX = 10000
MAX_PIXELS = 50_000_000


def max_image_bytes() -> int:
    try:
        return max(1, int(os.environ.get("MUNIM_INVOICE_MAX_BYTES", 8 * 1024 * 1024)))
    except ValueError:
        return 8 * 1024 * 1024


@dataclass(frozen=True)
class ImageInfo:
    mime_type: str
    width: int
    height: int


def sniff_format(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            return None
        marker = data[index + 1]
        if marker == 0xFF:
            index += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        length = struct.unpack(">H", data[index + 2:index + 4])[0]
        if length < 2:
            return None
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[index + 5:index + 9])
            return width, height
        index += 2 + length
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def validate_invoice_image(data: bytes, declared_type: str | None) -> ImageInfo:
    declared = (declared_type or "").split(";", 1)[0].strip().lower()
    if not data:
        raise HTTPException(status_code=400, detail="Invoice image is empty.")
    limit = max_image_bytes()
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"Invoice image exceeds the {limit // (1024 * 1024)} MB upload limit.")
    if declared not in ALLOWED_DECLARED:
        raise HTTPException(status_code=415, detail="Unsupported invoice file type. Upload a JPEG, PNG, or WebP photo.")
    sniffed = sniff_format(data)
    if sniffed is None:
        raise HTTPException(status_code=415, detail="File is not a readable JPEG, PNG, or WebP image.")
    if declared.startswith("image/") and declared.replace("image/jpg", "image/jpeg") != sniffed:
        raise HTTPException(status_code=415, detail="Declared file type does not match the image contents.")
    size = {"image/png": _png_size, "image/jpeg": _jpeg_size, "image/webp": _webp_size}[sniffed](data)
    if size is None:
        raise HTTPException(status_code=422, detail="Image header is malformed; dimensions could not be read.")
    width, height = size
    if min(width, height) < MIN_SIDE_PX:
        raise HTTPException(status_code=422, detail=f"Image is too small to read ({width}x{height}); minimum side is {MIN_SIDE_PX}px.")
    if max(width, height) > MAX_SIDE_PX or width * height > MAX_PIXELS:
        raise HTTPException(status_code=413, detail=f"Image dimensions {width}x{height} exceed the allowed limit.")
    return ImageInfo(mime_type=sniffed, width=width, height=height)
