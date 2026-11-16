# -*- coding: utf-8 -*-
"""生成一张 200x120 的测试贴图：四个色块加斜向渐变，尺寸故意的非 2 次幂。"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 200, 120


def chunk(tag, body):
    return (struct.pack(">I", len(body)) + tag + body +
            struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))


def make():
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        for x in range(W):
            qx = 0 if x < W // 2 else 1
            qy = 0 if y < H // 2 else 1
            base = [(220, 60, 60), (60, 180, 90), (70, 110, 220), (230, 200, 80)][qy * 2 + qx]
            t = (x + y) / float(W + H)
            rgba = (int(base[0] * (0.4 + 0.6 * t)), int(base[1] * (0.4 + 0.6 * t)),
                    int(base[2] * (0.4 + 0.6 * t)), 255)
            raw.extend(rgba)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "texture.png")
    with open(path, "wb") as f:
        f.write(data)
    print("已生成", path, W, "x", H)


if __name__ == "__main__":
    make()
