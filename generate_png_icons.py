#!/usr/bin/env python3
import os
import struct
import zlib

def make_png(width, height, color_rgb=(99, 102, 241)):
    r, g, b = color_rgb
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # no filter
        for x in range(width):
            raw_data.extend([r, g, b])
    
    compressed = zlib.compress(raw_data)
    
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend

out_dir = "/home/well/.gemini/antigravity/scratch/ai_council_automation/extension/icons"
os.makedirs(out_dir, exist_ok=True)

for size in [16, 48, 128]:
    path = os.path.join(out_dir, f"icon-{size}.png")
    with open(path, "wb") as f:
        f.write(make_png(size, size))
    print(f"Generated PNG icon: {path}")
