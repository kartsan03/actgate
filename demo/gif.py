"""Pack PNG frames into a GIF. Pillow merges identical frames; this does not.

Drops frames whose pixels did not change, except every 8th, so the caret
still blinks on a hold. One 32-color palette for the whole strip.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PIL import Image


def lzw(indexes: bytes, min_code_size: int) -> bytes:
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    next_code = eoi + 1
    table = {bytes([i]): i for i in range(clear)}
    bit_buf = 0
    bit_n = 0
    out = bytearray()

    def write(code: int) -> None:
        nonlocal bit_buf, bit_n
        bit_buf |= code << bit_n
        bit_n += code_size
        while bit_n >= 8:
            out.append(bit_buf & 0xFF)
            bit_buf >>= 8
            bit_n -= 8

    write(clear)
    w = b""
    for byte in indexes:
        k = bytes([byte])
        wk = w + k
        if wk in table:
            w = wk
            continue
        write(table[w])
        if next_code < 4096:
            table[wk] = next_code
            next_code += 1
            # Width grows when the code just assigned fills the current width.
            if next_code > (1 << code_size) and code_size < 12:
                code_size += 1
        else:
            write(clear)
            table = {bytes([i]): i for i in range(clear)}
            code_size = min_code_size + 1
            next_code = eoi + 1
        w = k
    if w:
        write(table[w])
    write(eoi)
    if bit_n:
        out.append(bit_buf & 0xFF)
    packed = bytearray()
    for i in range(0, len(out), 255):
        chunk = out[i : i + 255]
        packed.append(len(chunk))
        packed.extend(chunk)
    packed.append(0)
    return bytes([min_code_size]) + bytes(packed)


def main() -> int:
    frames_dir, gif_path = Path(sys.argv[1]), Path(sys.argv[2])
    frames = sorted(frames_dir.glob("f*.png"))
    if not frames:
        print("no frames", file=sys.stderr)
        return 1
    first = Image.open(frames[0])
    w, h = first.size

    kept: list[Image.Image] = []
    prev: bytes | None = None
    for i, path in enumerate(frames):
        im = Image.open(path).convert("RGB")
        raw = im.tobytes()
        if raw != prev or i % 8 == 0 or i == len(frames) - 1:
            kept.append(im)
            prev = raw

    sheet = Image.new("RGB", (w, h * 4))
    for i, idx in enumerate([0, len(kept) // 3, 2 * len(kept) // 3, len(kept) - 1]):
        sheet.paste(kept[idx], (0, i * h))
    pal_img = sheet.quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    palette = bytes(pal_img.getpalette()[: 32 * 3])

    # 32 colors: packed field size = 4. Delay is 8cs, close to the 15fps source.
    header = b"GIF89a" + struct.pack("<HH", w, h) + bytes([0xF4, 0, 0])
    loop = b"!\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00"
    parts = [header, palette, loop]
    for im in kept:
        blob = im.quantize(palette=pal_img, dither=Image.Dither.NONE).tobytes()
        gce = b"!\xF9\x04" + bytes([0x04]) + struct.pack("<H", 8) + bytes([0, 0])
        desc = b"," + struct.pack("<HHHH", 0, 0, w, h) + bytes([0])
        parts.append(gce + desc + lzw(blob, 5))
    parts.append(b";")
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    gif_path.write_bytes(b"".join(parts))
    print(f"{len(kept)} {gif_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
