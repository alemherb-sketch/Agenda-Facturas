"""Genera iconos PWA PNG sin dependencias externas."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "static" / "icons"


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: Path, size: int, rgba_fn) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(rgba_fn(x, y, size))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(data)


def color(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    # Fondo verde marca + monograma AF simplificado
    cx, cy = size / 2, size / 2
    dx, dy = x - cx, y - cy
    r = (dx * dx + dy * dy) ** 0.5
    radius = size * 0.46
    if r > radius:
        return (0, 0, 0, 0)
    # gradiente
    t = r / radius
    g = int(15 + (31 - 15) * (1 - t))
    b = int(61 + (107 - 61) * (1 - t))
    rr = int(46 + (79 - 46) * (1 - t))
    # acento ambar en esquina
    if x > size * 0.62 and y < size * 0.38 and r < radius:
        return (201, 133, 42, 255)
    # barra vertical del monograma
    if size * 0.30 < x < size * 0.40 and size * 0.28 < y < size * 0.72:
        return (255, 255, 255, 255)
    # barra horizontal
    if size * 0.30 < x < size * 0.68 and size * 0.28 < y < size * 0.38:
        return (255, 255, 255, 255)
    # segunda F
    if size * 0.48 < x < size * 0.58 and size * 0.40 < y < size * 0.72:
        return (255, 255, 255, 230)
    if size * 0.48 < x < size * 0.72 and size * 0.48 < y < size * 0.56:
        return (255, 255, 255, 230)
    return (g, b, rr, 255)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        write_png(OUT / f"icon-{size}.png", size, color)
    print(f"Iconos generados en {OUT}")


if __name__ == "__main__":
    main()
