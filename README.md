# mipmap 链生成

骨架能读写 8 位 RGBA 的 PNG，能生成一条 mip 链，但降采样质量与尺寸处理都有问题。

## 已知缺口

- `downsample` 用隔点取样，2x2 里只取左上角一个像素，高频纹理降到第二级就走样。
- 非 2 次幂尺寸（测试贴图是 200x120）一路整除下去会得到 100x60、50x30、25x15、12x7、6x3、3x1，
  尺寸序列不规整，最后一级也不是 1x1。
- 半透明像素的 RGB 没有预乘，直接平均会把透明区域的黑色混进边缘。
- `generate_chain` 算级数时没有下限保护，一张 1x1 的图会返回 1 级，与常规 mip 语义不一致。

## 运行

```
python gen_samples.py
python -m mip.cli data/texture.png --out-dir out
python -m pytest tests -q
```

测试贴图 200x120，四个象限四种颜色，叠了斜向渐变，用来检验降采样是否保留色块边界。
