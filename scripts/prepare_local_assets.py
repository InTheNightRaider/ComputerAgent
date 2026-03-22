from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / 'src-tauri' / 'icons'
ICON_DIR.mkdir(parents=True, exist_ok=True)


def png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: Path, size: int, bg=(10, 31, 68, 255), fg=(15, 203, 138, 255)) -> None:
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            inset = size // 8 <= x < size - size // 8 and size // 8 <= y < size - size // 8
            color = fg if inset else bg
            row.extend(color)
        rows.append(bytes(row))
    raw = b''.join(rows)
    ihdr = struct.pack('!IIBBBBB', size, size, 8, 6, 0, 0, 0)
    payload = b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', ihdr) + png_chunk(b'IDAT', zlib.compress(raw, 9)) + png_chunk(b'IEND', b'')
    path.write_bytes(payload)


def write_ico(path: Path, png_path: Path) -> None:
    png_data = png_path.read_bytes()
    header = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHII', 128, 128, 0, 0, 1, 32, len(png_data), 6 + 16)
    path.write_bytes(header + entry + png_data)




DEMO_INBOX = ROOT / 'demo_data' / 'Inbox'

def ensure_demo_files() -> None:
    DEMO_INBOX.mkdir(parents=True, exist_ok=True)
    samples = {
        'Quarterly_Report.pdf': 'Demo PDF placeholder for rename testing.\n',
        'Meeting Notes.pdf': 'Second demo PDF placeholder.\n',
        'screenshot1.png': 'PNG placeholder for move testing.\n',
        'screenshot2.png': 'PNG placeholder for move testing.\n',
        'photo_a.jpg': 'JPEG placeholder duplicate A.\n',
        'photo_b.jpg': 'JPEG placeholder duplicate A.\n',
    }
    for name, content in samples.items():
        path = DEMO_INBOX / name
        if not path.exists():
            path.write_text(content, encoding='utf-8')

def ensure_icons() -> None:
    png32 = ICON_DIR / '32x32.png'
    png128 = ICON_DIR / '128x128.png'
    ico = ICON_DIR / 'icon.ico'
    if not png32.exists():
        write_png(png32, 32)
    if not png128.exists():
        write_png(png128, 128)
    if not ico.exists():
        write_ico(ico, png128)


if __name__ == '__main__':
    ensure_demo_files()
    ensure_icons()
    print('Prepared local demo assets and Tauri icon assets.')
