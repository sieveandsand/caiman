#!/usr/bin/env python3
"""Build terminal Doto glyphs deterministically from the official variable font.

Build-only dependency: Pillow (FreeType support). The installed application has
no Pillow dependency. Supply --sha256 to verify the exact upstream artifact.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version


def braille(image):
    bits = ((0, 0, 0), (0, 1, 1), (0, 2, 2), (1, 0, 3),
            (1, 1, 4), (1, 2, 5), (0, 3, 6), (1, 3, 7))
    rows = []
    for y in range(0, image.height, 4):
        row = ""
        for x in range(0, image.width, 2):
            mask = sum(1 << bit for dx, dy, bit in bits
                       if x + dx < image.width and y + dy < image.height
                       and image.getpixel((x + dx, y + dy)) >= 96)
            row += chr(0x2800 + mask) if mask else " "
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, default=Path("src/caiman/assets/doto-atlas.json"))
    args = parser.parse_args()
    digest = hashlib.sha256(args.font.read_bytes()).hexdigest()
    if digest != args.sha256:
        parser.error("Font SHA-256 does not match the recorded upstream artifact")
    chars = "".join(chr(code) for code in range(32, 127))
    sizes = []
    for pixels in (16, 24, 32):
        font = ImageFont.truetype(str(args.font), pixels)
        # Doto's variable axes are queried by name rather than assumed order.
        axes = font.get_variation_axes()
        values = [axis["maximum"] if axis["name"] in (b"Weight", b"Roundness") else axis["default"] for axis in axes]
        font.set_variation_by_axes(values)
        top = min(font.getbbox(char)[1] for char in chars)
        bottom = max(font.getbbox(char)[3] for char in chars)
        height = math.ceil((bottom - top) / 4) * 4
        glyphs = {}
        for char in chars:
            left, _, right, _ = font.getbbox(char)
            width = math.ceil((max(font.getlength(char), right) - min(left, 0)) / 2) * 2
            image = Image.new("L", (max(width, 2), height))
            ImageDraw.Draw(image).text((-min(left, 0), -top), char, font=font, fill=255)
            glyphs[char] = braille(image)
        sizes.append({"pixels": pixels, "rows": height // 4, "glyphs": glyphs})
    data = {"font": "Doto", "font_sha256": digest,
            "source": "https://github.com/google/fonts/tree/main/ofl/doto",
            "pillow_version": pillow_version, "sizes": sizes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
