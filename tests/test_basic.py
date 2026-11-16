# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mip.core import Image, downsample, generate_chain  # noqa: E402


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
