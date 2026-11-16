# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mip.core import Image, downsample, generate_chain, load_png, save_png  # noqa: E402


def test_downsample_size():
    img = Image(8, 8)
    small = downsample(img)
    assert small.width == 4
    assert small.height == 4


def test_chain_level_count():
    img = Image(16, 16)
    levels = generate_chain(img)
    assert levels[0].width == 16
    assert levels[-1].width == 1
    assert len(levels) == 5


def test_chain_custom_max():
    img = Image(64, 64)
    levels = generate_chain(img, max_levels=3)
    assert len(levels) == 3
    assert (levels[-1].width, levels[-1].height) == (16, 16)


def test_size_sequence_non_power_of_two():
    """200x120 每级宽高 = ceil(上级/2)，收敛到 1x1，任何一维不先归零。"""
    levels = generate_chain(Image(200, 120))
    sizes = [(lv.width, lv.height) for lv in levels]
    assert sizes == [
        (200, 120), (100, 60), (50, 30), (25, 15),
        (13, 8), (7, 4), (4, 2), (2, 1), (1, 1),
    ]
    for w, h in sizes:
        assert w >= 1 and h >= 1


def test_downsample_box_average():
    """2x2 四色图降到 1x1，结果必须是四色平均而非单点取样。"""
    img = Image(2, 2, [
        (0, 0, 0, 255), (100, 0, 0, 255),
        (0, 100, 0, 255), (0, 0, 200, 255),
    ])
    out = downsample(img)
    assert (out.width, out.height) == (1, 1)
    # (0+100+0+0)/4=25, (0+0+100+0)/4=25, (0+0+0+200)/4=50
    assert out.at(0, 0) == (25, 25, 50, 255)


def test_alpha_edge_no_black_bleed():
    """不透明红 + 全透明黑 平均后仍是纯红，透明度减半，不混黑。"""
    img = Image(2, 1, [
        (255, 0, 0, 255), (0, 0, 0, 0),
    ])
    out = downsample(img)
    r, g, b, a = out.at(0, 0)
    assert (r, g, b) == (255, 0, 0)
    assert a == 128  # (255 + 0 + 1) // 2，四舍五入


def test_fully_transparent_region():
    img = Image(2, 2, [(10, 20, 30, 0)] * 4)
    out = downsample(img)
    assert out.at(0, 0) == (0, 0, 0, 0)


def test_max_levels_truncates():
    levels = generate_chain(Image(64, 64), max_levels=4)
    assert len(levels) == 4
    assert (levels[-1].width, levels[-1].height) == (8, 8)


def test_max_levels_one_keeps_source():
    levels = generate_chain(Image(64, 64), max_levels=1)
    assert len(levels) == 1
    assert (levels[0].width, levels[0].height) == (64, 64)


def test_single_pixel_input():
    """1x1 输入返回单级链，不抛异常、不为空。"""
    img = Image(1, 1, [(7, 8, 9, 255)])
    levels = generate_chain(img)
    assert len(levels) == 1
    assert levels[0].at(0, 0) == (7, 8, 9, 255)


def test_extreme_aspect_ratio_converges():
    """16x1 这类细长图也要收敛到 1x1。"""
    levels = generate_chain(Image(16, 1))
    sizes = [(lv.width, lv.height) for lv in levels]
    assert sizes == [(16, 1), (8, 1), (4, 1), (2, 1), (1, 1)]


def test_save_png_deterministic(tmp_path):
    """同一输入写两次，输出逐字节相同。"""
    img = Image(4, 4, [(x * 16, y * 16, 128, 255)
                       for y in range(4) for x in range(4)])
    p1 = str(tmp_path / "a.png")
    p2 = str(tmp_path / "b.png")
    save_png(img, p1)
    save_png(img, p2)
    with open(p1, "rb") as f:
        b1 = f.read()
    with open(p2, "rb") as f:
        b2 = f.read()
    assert b1 == b2


def test_save_load_roundtrip(tmp_path):
    img = Image(3, 2, [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12),
                       (13, 14, 15, 16), (17, 18, 19, 20), (21, 22, 23, 24)])
    p = str(tmp_path / "rt.png")
    save_png(img, p)
    back = load_png(p)
    assert (back.width, back.height) == (3, 2)
    assert back.pixels == img.pixels
