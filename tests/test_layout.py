"""排样算法验证：python tests/test_layout.py（纯标准库，无需安装依赖）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.layout import EPS, LabelType, layout_labels  # noqa: E402


def overlap(a, b):
    return (
        a.x < b.x + b.width - EPS
        and a.x + a.width > b.x + EPS
        and a.y < b.y + b.height - EPS
        and a.y + a.height > b.y + EPS
    )


def check_page(placements, cw, ch, gap_x, gap_y):
    """校验：不出界 + 任意两个标签互不重叠（内容矩形按间距要求分离）。"""
    for i, p in enumerate(placements):
        w, h = (p.height, p.width) if p.rotated else (p.width, p.height)
        assert p.x >= -EPS and p.y >= -EPS, f"标签越界(左上): {p}"
        assert p.x + w <= cw + EPS, f"标签越界(右): {p} cw={cw}"
        assert p.y + h <= ch + EPS, f"标签越界(下): {p} ch={ch}"

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            aw = a.height if a.rotated else a.width
            ah = a.width if a.rotated else a.height
            bw = b.height if b.rotated else b.width
            bh = b.width if b.rotated else b.height
            ra = type("R", (), {"x": a.x, "y": a.y, "width": aw, "height": ah})
            rb = type("R", (), {"x": b.x, "y": b.y, "width": bw, "height": bh})
            assert not overlap(ra, rb), (
                f"标签重叠:\n {vars(a)}\n {vars(b)}"
            )
            # 间距校验：若水平投影重叠，则纵向至少隔 gap_y；反之亦然
            x_sep = (a.x + aw <= b.x + EPS) or (b.x + bw <= a.x + EPS)
            y_sep = (a.y + ah <= b.y + EPS) or (b.y + bh <= a.y + EPS)
            if not x_sep:
                gap = abs((b.y if a.y < b.y else a.y) -
                          (a.y + ah if a.y < b.y else b.y + bh))
                assert gap >= gap_y - EPS, f"纵向间距不足 {gap} < {gap_y}"
            if not y_sep:
                gap = abs((b.x if a.x < b.x else a.x) -
                          (a.x + aw if a.x < b.x else b.x + bw))
                assert gap >= gap_x - EPS, f"横向间距不足 {gap} < {gap_x}"


def test_single_page_packing():
    labels = [LabelType("L", 60, 40, 18)]
    r = layout_labels(labels, 210, 297, 5, 5, 5, 5, 2, 2, False)
    cw, ch = 200, 287
    assert len(r.pages) == 1
    check_page(r.pages[0].placements, cw, ch, 2, 2)
    # 宽向 floor((200+2)/62)=3，高向 floor((287+2)/42)=6 -> 18
    assert r.planned[0] == 18, r.planned
    print("✓ test_single_page_packing: 单页 18 枚，无重叠不出界")


def test_rotation_enables_more():
    # 100x60 标签：纵向 A4 可打印区 200x287
    labels = [LabelType("R", 100, 60, 10)]
    no_rot = layout_labels(labels, 210, 297, 5, 5, 5, 5, 0, 0, False)
    rotated = layout_labels(labels, 210, 297, 5, 5, 5, 5, 0, 0, True)
    n_no = sum(len(p.placements) for p in no_rot.pages)
    n_rot = sum(len(p.placements) for p in rotated.pages)
    assert n_rot >= n_no
    for page in rotated.pages:
        check_page(page.placements, 200, 287, 0, 0)
    print(f"✓ test_rotation_enables_more: 不旋转 {n_no} 枚 → 允许旋转 {n_rot} 枚")


def test_multi_page_continuation():
    labels = [LabelType("Big", 100, 130, 5), LabelType("Small", 40, 30, 30)]
    r = layout_labels(labels, 210, 297, 10, 10, 10, 10, 3, 3, True)
    assert len(r.pages) >= 2, "放不下应自动续页"
    for page in r.pages:
        check_page(page.placements, 190, 277, 3, 3)
    placed_big = sum(1 for p in r.pages for q in p.placements
                     if q.type_index == 0)
    placed_small = sum(1 for p in r.pages for q in p.placements
                       if q.type_index == 1)
    assert placed_big == 5 and placed_small == 30
    print(f"✓ test_multi_page_continuation: {len(r.pages)} 页，全部排入")


def test_oversize_skipped():
    labels = [LabelType("Huge", 300, 300, 2), LabelType("Ok", 50, 50, 4)]
    r = layout_labels(labels, 210, 297, 5, 5, 5, 5, 0, 0, True)
    assert r.oversize[0] is True
    assert r.planned[0] == 0
    assert r.planned[1] == 4
    assert any("超出单页" in w for w in r.warnings)
    print("✓ test_oversize_skipped: 超大标签被跳过并告警")


def test_max_sheets_limit():
    labels = [LabelType("L", 80, 80, 100)]
    r = layout_labels(labels, 210, 297, 5, 5, 5, 5, 2, 2, True, max_sheets=2)
    assert len(r.pages) == 2
    assert r.planned[0] < 100
    assert any("最大页数" in w for w in r.warnings)
    for page in r.pages:
        check_page(page.placements, 200, 287, 2, 2)
    print(f"✓ test_max_sheets_limit: 限 2 页，排入 {r.planned[0]} 枚并告警")


def test_sequences_per_type():
    labels = [LabelType("A", 50, 50, 3), LabelType("B", 60, 60, 3)]
    r = layout_labels(labels, 210, 297, 5, 5, 5, 5, 0, 0, True)
    seqs = {0: set(), 1: set()}
    for page in r.pages:
        for p in page.placements:
            seqs[p.type_index].add(p.sequence)
    assert seqs[0] == {1, 2, 3} and seqs[1] == {1, 2, 3}
    print("✓ test_sequences_per_type: 各类型序号连续 1..N")


def test_zero_gap_edge():
    # 零间距：最后一列右边应正好落在可打印区边界
    labels = [LabelType("L", 50, 50, 16)]
    r = layout_labels(labels, 200, 200, 0, 0, 0, 0, 0, 0, False)
    assert len(r.pages) == 1
    assert r.planned[0] == 16  # 4x4 恰好铺满
    maxx = max(p.x + (p.height if p.rotated else p.width)
               for p in r.pages[0].placements)
    maxy = max(p.y + (p.width if p.rotated else p.height)
               for p in r.pages[0].placements)
    assert abs(maxx - 200) < EPS and abs(maxy - 200) < EPS, (maxx, maxy)
    print("✓ test_zero_gap_edge: 零间距恰好贴边铺满，无重复间距")


if __name__ == "__main__":
    test_single_page_packing()
    test_rotation_enables_more()
    test_multi_page_continuation()
    test_oversize_skipped()
    test_max_sheets_limit()
    test_sequences_per_type()
    test_zero_gap_edge()
    print("\n全部测试通过 ✅")
