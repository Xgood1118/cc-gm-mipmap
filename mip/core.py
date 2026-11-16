# -*- coding: utf-8 -*-
"""mipmap 链生成骨架。

降采样用的是隔点取样，级数固定算到 1x1，不处理非 2 次幂尺寸。
"""

import struct
import zlib


class Image(object):
    def __init__(self, width, height, pixels=None):
        self.width = int(width)
        self.height = int(height)
        if pixels is None:
            self.pixels = [(0, 0, 0, 255)] * (self.width * self.height)
        else:
            self.pixels = pixels

    def at(self, x, y):
        return self.pixels[y * self.width + x]

    def set(self, x, y, rgba):
        self.pixels[y * self.width + x] = rgba


def load_png(path):
    """读取 PNG。当前只认 8 位 RGBA 非隔行，其余直接抛错。"""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    pos = 8
    width = height = bit = ctype = None
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctag == b"IHDR":
            width, height, bit, ctype = struct.unpack(">IIBB", body[:10])
        elif ctag == b"IDAT":
            idat += body
        elif ctag == b"IEND":
            break
    if bit != 8 or ctype != 6:
        raise ValueError("只支持 8 位 RGBA")
    raw = zlib.decompress(idat)
    stride = width * 4
    pixels = []
    prev = bytearray(stride)
    p = 0
    for _y in range(height):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(4, stride):
                line[i] = (line[i] + line[i - 4]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft != 0:
            raise ValueError("不支持的过滤类型 %d" % ft)
        for x in range(width):
            pixels.append(tuple(line[x * 4:x * 4 + 4]))
        prev = line
    return Image(width, height, pixels)


def save_png(img, path):
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)
        for x in range(img.width):
            raw.extend(img.at(x, y))
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 6, 0, 0, 0)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(out)


def downsample(img):
    """降一半。当前隔点取样，不做平均。"""
    w = max(1, img.width // 2)
    h = max(1, img.height // 2)
    out = Image(w, h)
    for y in range(h):
        for x in range(w):
            out.set(x, y, img.at(min(x * 2, img.width - 1), min(y * 2, img.height - 1)))
    return out


def generate_chain(img, max_levels=None):
    """生成 mip 链。级数算到 1x1，非 2 次幂尺寸不补齐。"""
    levels = [img]
    cur = img
    while cur.width > 1 and cur.height > 1:
        if max_levels is not None and len(levels) >= max_levels:
            break
        cur = downsample(cur)
        levels.append(cur)
    return levels


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="mip")
    ap.add_argument("png")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--levels", type=int, default=None)
    args = ap.parse_args(argv)
    img = load_png(args.png)
    levels = generate_chain(img, args.levels)
    import os
    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)
    for i, lv in enumerate(levels):
        save_png(lv, os.path.join(args.out_dir, "level_%02d.png" % i))
    print("生成 %d 级，尺寸从 %dx%d 到 %dx%d" % (
        len(levels), levels[0].width, levels[0].height, levels[-1].width, levels[-1].height))
    return 0
