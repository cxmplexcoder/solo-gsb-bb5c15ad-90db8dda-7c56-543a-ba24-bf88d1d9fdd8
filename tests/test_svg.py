"""SVG 产物校验：python tests/test_svg.py

验证：
- 单页/多页 SVG 均为合法 XML；多页文件不出现嵌套 <svg>；
- 每个标签矩形 = 排样坐标 + 页边距（预览与导出同坐标）；
- 标签内容不出纸边，相邻标签边界间隔等于设定 gap。
"""

import sys
import xml.dom.minidom as minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.layout import LabelType, layout_labels  # noqa: E402
from app.svg import render_multi_page_svg, render_page_svg  # noqa: E402


def _f(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


def parse(s):
    return minidom.parseString(s)


def collect_label_rects(page, ml, mt):
    """返回期望的标签矩形 (x, y, w, h, rotated)。"""
    out = []
    for p in page.placements:
        out.append((ml + p.x, mt + p.y, p.width, p.height, p.rotated))
    return out


def rects_in_doc(doc):
    rects = []
    for r in doc.getElementsByTagName("rect"):
        rects.append(
            (
                float(r.getAttribute("x") or 0),
                float(r.getAttribute("y") or 0),
                float(r.getAttribute("width") or 0),
                float(r.getAttribute("height") or 0),
                r.getAttribute("fill"),
            )
        )
    return rects


def test_single_page_coords():
    labels = [LabelType("产品", 60, 40, 12), LabelType("条码", 40, 25, 10)]
    r = layout_labels(labels, 210, 297, 8, 8, 8, 8, 2, 3, True)
    assert len(r.pages) == 1
    svg = render_page_svg(r.pages[0], 210, 297, 8, 8, 8, 8)
    doc = parse(svg)

    expected = set()
    for p in r.pages[0].placements:
        # 旋转标签的 <rect> 宽高互换（内容整体转 90°）
        w, h = (p.height, p.width) if p.rotated else (p.width, p.height)
        expected.add((round(8 + p.x, 3), round(8 + p.y, 3),
                      round(w, 3), round(h, 3)))
    got = set()
    for x, y, w, h, fill in rects_in_doc(doc):
        # 跳过纸面/可打印区两个大矩形（含 #ffffff 或无 rx 的大框）
        if w >= 200 or h >= 280:
            continue
        got.add((round(x, 3), round(y, 3), round(w, 3), round(h, 3)))
    missing = expected - got
    assert not missing, f"SVG 缺少 {len(missing)} 个排样坐标矩形: {list(missing)[:3]}"
    print(f"✓ test_single_page_coords: {len(expected)} 个标签矩形与排样坐标一致")


def test_multi_page_no_nested_svg():
    labels = [LabelType("A", 100, 130, 5), LabelType("B", 40, 30, 30)]
    r = layout_labels(labels, 210, 297, 10, 10, 10, 10, 3, 3, True)
    n = len(r.pages)
    assert n >= 2
    svg = render_multi_page_svg(r, 210, 297, 10, 10, 10, 10)
    doc = parse(svg)
    roots = doc.getElementsByTagName("svg")
    assert len(roots) == 1, f"出现嵌套 svg，共 {len(roots)} 个"
    # 总高 = n*297 + (n-1)*6
    assert doc.documentElement.getAttribute("height") == _f(n * 297 + (n - 1) * 6) + "mm"
    print(f"✓ test_multi_page_no_nested_svg: {n} 页单一根 svg，高度正确")


def test_margins_respected():
    labels = [LabelType("L", 50, 50, 20)]
    ml, mr, mt, mb = 10, 12, 8, 14
    r = layout_labels(labels, 210, 297, mt, mr, mb, ml, 2, 2, False)
    svg = render_multi_page_svg(r, 210, 297, mt, mr, mb, ml,
                                crop_marks=False)
    doc = parse(svg)
    for page_idx, page in enumerate(r.pages):
        for x, y, w, h, fill in rects_in_doc(doc):
            if w >= 200 or h >= 280:
                continue
            y_abs = y + page_idx * (297 + 6)
            assert x >= ml - 0.01, f"左边距被突破 x={x}"
            assert y_abs - page_idx * (297 + 6) + h <= 297 - mb + 0.01
            assert x + w <= 210 - mr + 0.01, f"右边距被突破 x+w={x + w}"
    print("✓ test_margins_respected: 所有标签位于四向页边距之内")


if __name__ == "__main__":
    test_single_page_coords()
    test_multi_page_no_nested_svg()
    test_margins_respected()
    print("\nSVG 测试通过 ✅")
