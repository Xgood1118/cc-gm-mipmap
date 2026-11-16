# -*- coding: utf-8 -*-
"""mipmap 链生成器。

- 降采样：2x2 区域平均（box filter），奇数尺寸边缘自动裁剪为 2x1 / 1x2 / 1x1。
- 透明度：按 alpha 预乘加权平均，半透明边缘不会混入透明像素的 RGB。
- 尺寸：每级宽高 = ceil(上一级 / 2)，奇数维度也能收敛到 1x1，不会先归零。
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


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def load_png(path):
    """读取 PNG。只认 8 位 RGBA 非隔行，支持全部 5 种行过滤类型。"""
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
        if ft == 1:  # Sub
            for i in range(4, stride):
                line[i] = (line[i] + line[i - 4]) & 0xFF
        elif ft == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:  # Average
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:  # Paeth
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                up_left = prev[i - 4] if i >= 4 else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        elif ft != 0:
            raise ValueError("不支持的过滤类型 %d" % ft)
        for x in range(width):
            pixels.append(tuple(line[x * 4:x * 4 + 4]))
        prev = line
    return Image(width, height, pixels)


def save_png(img, path):
    """写出 8 位 RGBA PNG。固定过滤类型 0、固定压缩级别，输出逐字节确定。"""
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)
        for x in range(img.width):
            raw.extend(img.at(x, y))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 6, 0, 0, 0)
    out = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(out)


def _box_average(img, x0, y0, x1, y1):
    """对 [x0,x1) x [y0,y1) 区域做 alpha 预乘加权平均，返回 (r,g,b,a)。"""
    n = 0
    sr = sg = sb = sa = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = img.at(x, y)
            sr += r * a
            sg += g * a
            sb += b * a
            sa += a
            n += 1
    a_out = (sa + n // 2) // n
    if sa > 0:
        # 预乘平均：颜色按 alpha 加权，透明像素的颜色不参与
        r_out = (sr + sa // 2) // sa
        g_out = (sg + sa // 2) // sa
        b_out = (sb + sa // 2) // sa
    else:
        # 全透明区域没有可见颜色，直接置零
        r_out = g_out = b_out = 0
    return (r_out, g_out, b_out, a_out)


def downsample(img):
    """宽高各减半（向上取整），每个目标像素对 2x2 源区域做预乘加权平均。"""
    w = (img.width + 1) // 2
    h = (img.height + 1) // 2
    out = Image(w, h)
    for y in range(h):
        y0 = y * 2
        y1 = min(y0 + 2, img.height)
        for x in range(w):
            x0 = x * 2
            x1 = min(x0 + 2, img.width)
            out.set(x, y, _box_average(img, x0, y0, x1, y1))
    return out


def generate_chain(img, max_levels=None):
    """生成 mip 链，从原图一路降到 1x1。

    max_levels 给定则截断到该级数（至少保留原图这 1 级）。
    1x1 输入返回仅含原图的单级链。
    """
    if max_levels is not None and max_levels < 1:
        raise ValueError("max_levels 必须 >= 1")
    levels = [img]
    cur = img
    while cur.width > 1 or cur.height > 1:
        if max_levels is not None and len(levels) >= max_levels:
            break
        cur = downsample(cur)
        levels.append(cur)
    return levels


def main(argv=None):
    import argparse
    import os
    ap = argparse.ArgumentParser(prog="mip")
    ap.add_argument("png")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--levels", type=int, default=None)
    args = ap.parse_args(argv)
    img = load_png(args.png)
    levels = generate_chain(img, args.levels)
    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)
    for i, lv in enumerate(levels):
        save_png(lv, os.path.join(args.out_dir, "level_%02d.png" % i))
    print("生成 %d 级，尺寸从 %dx%d 到 %dx%d" % (
        len(levels), levels[0].width, levels[0].height,
        levels[-1].width, levels[-1].height))
    return 0
