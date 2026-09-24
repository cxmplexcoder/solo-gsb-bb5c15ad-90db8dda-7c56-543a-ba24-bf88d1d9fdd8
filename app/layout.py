"""标签拼版核心：基于 MaxRects（BSSF）的毫米坐标排样算法。

- 全部尺寸单位均为毫米（mm），浮点运算。
- 每张标签在排样时按 (w + gap_x, h + gap_y) 分配"槽位"，
  内容区在槽位左上角，因此相邻标签之间恰好留出一个间距，
  纸边也正好停在页边距处（最后一列/行不重复叠加间距）。
- 支持在 allow_rotate=True 时把标签旋转 90 度尝试。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

EPS = 1e-6


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Rect:
    """矩形槽位（mm）。"""

    x: float
    y: float
    w: float
    h: float


@dataclass
class LabelType:
    """一种标签规格。"""

    name: str
    width: float
    height: float
    quantity: int


@dataclass
class Placement:
    """单个标签在某张纸上的摆放结果。"""

    type_index: int
    name: str
    width: float          # 实际内容宽（未旋转方向）
    height: float         # 实际内容高
    x: float              # 相对可打印区左上角
    y: float
    rotated: bool
    sequence: int         # 该种类内的序号（从 1 开始）
    color: str = "#cfe8ff"


@dataclass
class Page:
    """一张纸的排样结果（坐标相对可打印区）。"""

    placements: List[Placement]
    content_width: float
    content_height: float
    used_area: float
    fill_ratio: float


@dataclass
class LayoutResult:
    pages: List[Page]
    planned: List[int]    # 每种标签实际排入数量
    requested: List[int]  # 每种标签需求数量
    oversize: List[bool]  # 该种标签即使旋转也放不下单张纸
    warnings: List[str]


# --------------------------------------------------------------------------- #
# 基础几何
# --------------------------------------------------------------------------- #
def _intersects(a: Rect, b: Rect) -> bool:
    return (
        a.x < b.x + b.w - EPS
        and a.x + a.w > b.x + EPS
        and a.y < b.y + b.h - EPS
        and a.y + a.h > b.y + EPS
    )


def _contains(outer: Rect, inner: Rect) -> bool:
    return (
        inner.x >= outer.x - EPS
        and inner.y >= outer.y - EPS
        and inner.x + inner.w <= outer.x + outer.w + EPS
        and inner.y + inner.h <= outer.y + outer.h + EPS
    )


# --------------------------------------------------------------------------- #
# MaxRects
# --------------------------------------------------------------------------- #
class MaxRects:
    """单张纸的 MaxRects 排样器（Best Short Side Fit）。"""

    def __init__(self, width: float, height: float, gap_x: float, gap_y: float):
        # 可打印区向"右/下"各扩一个间距：槽位可以贴到外扩边界，
        # 但内容区域仍在原始可打印区内。
        self.width = width
        self.height = height
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.free: List[Rect] = [Rect(0.0, 0.0, width + gap_x, height + gap_y)]

    def _score_bssf(self, fr: Rect, w: float, h: float) -> Tuple[float, float]:
        """BSSF 评分：先比较短边余量，再比较长边余量，越小越优。"""
        if fr.w < w - EPS or fr.h < h - EPS:
            return (float("inf"), float("inf"))
        leftover_w = fr.w - w
        leftover_h = fr.h - h
        return (
            min(leftover_w, leftover_h),
            max(leftover_w, leftover_h),
        )

    def insert(self, w: float, h: float, allow_rotate: bool) -> Optional[Tuple[Rect, bool]]:
        """尝试放入宽 w 高 h 的标签，返回（槽位矩形, 是否旋转）。

        槽位尺寸为 (w+gap_x, h+gap_y)；旋转时内容互换而间距方向不变。
        """
        best: Optional[Rect] = None
        best_score: Tuple[float, float] = (float("inf"), float("inf"))
        best_rotated = False

        candidates: List[Tuple[float, float, bool]] = [
            (w + self.gap_x, h + self.gap_y, False),
        ]
        if allow_rotate and abs(w - h) > EPS:
            candidates.append((h + self.gap_x, w + self.gap_y, True))

        for slot_w, slot_h, rotated in candidates:
            for fr in self.free:
                score = self._score_bssf(fr, slot_w, slot_h)
                if score < best_score:
                    best_score = score
                    best = fr
                    best_rotated = rotated

        if best is None:
            return None

        if best_rotated:
            slot_w, slot_h = h + self.gap_x, w + self.gap_y
        else:
            slot_w, slot_h = w + self.gap_x, h + self.gap_y

        node = Rect(best.x, best.y, slot_w, slot_h)
        self._split_free(node)
        return node, best_rotated

    def _split_free(self, used: Rect) -> None:
        """用已占用槽位切割所有相交的空闲矩形。"""
        new_free: List[Rect] = []
        for fr in self.free:
            if _intersects(fr, used):
                # 左
                if used.x > fr.x + EPS:
                    new_free.append(
                        Rect(fr.x, fr.y, used.x - fr.x, fr.h)
                    )
                # 右
                if used.x + used.w < fr.x + fr.w - EPS:
                    new_free.append(
                        Rect(used.x + used.w, fr.y,
                             fr.x + fr.w - (used.x + used.w), fr.h)
                    )
                # 上（y 较小一侧）
                if used.y > fr.y + EPS:
                    new_free.append(
                        Rect(fr.x, fr.y, fr.w, used.y - fr.y)
                    )
                # 下（y 较大一侧）
                if used.y + used.h < fr.y + fr.h - EPS:
                    new_free.append(
                        Rect(fr.x, used.y + used.h,
                             fr.w, fr.y + fr.h - (used.y + used.h))
                    )
            else:
                new_free.append(fr)

        self.free = self._prune(new_free)

    @staticmethod
    def _prune(rects: List[Rect]) -> List[Rect]:
        """删除被其他空闲矩形完全包含的冗余矩形。"""
        result: List[Rect] = []
        for i, ri in enumerate(rects):
            dominated = False
            for j, rj in enumerate(rects):
                if i == j:
                    continue
                if _contains(rj, ri):
                    # 全等时保留索引较小的一个，避免互相误删
                    if abs(rj.w - ri.w) <= EPS and abs(rj.h - ri.h) <= EPS:
                        if _contains(ri, rj) and j < i:
                            dominated = True
                            break
                    else:
                        dominated = True
                        break
            if not dominated:
                result.append(ri)
        return result


# --------------------------------------------------------------------------- #
# 多页排样
# --------------------------------------------------------------------------- #
def layout_labels(
    labels: Sequence[LabelType],
    page_width: float,
    page_height: float,
    margin_top: float,
    margin_right: float,
    margin_bottom: float,
    margin_left: float,
    gap_x: float,
    gap_y: float,
    allow_rotate: bool,
    max_sheets: int = 0,
) -> LayoutResult:
    """把多种标签排入多张纸。

    排样顺序按单标签面积（含间距槽位）从大到小——大件先排是排样问题的
    常规策略，能显著提高填充率；同一种标签始终连续编号。
    max_sheets 为 0 表示不限页数。
    """
    content_w = page_width - margin_left - margin_right
    content_h = page_height - margin_top - margin_bottom

    requested = [t.quantity for t in labels]
    planned = [0] * len(labels)
    oversize = [False] * len(labels)
    warnings: List[str] = []

    for i, t in enumerate(labels):
        fits_normal = t.width <= content_w + EPS and t.height <= content_h + EPS
        fits_rotated = allow_rotate and (
            t.height <= content_w + EPS and t.width <= content_h + EPS
        )
        if not (fits_normal or fits_rotated):
            oversize[i] = True
            warnings.append(
                f"标签“{t.name}”（{_fmt(t.width)}×{_fmt(t.height)}mm）"
                f"超出单页可打印区，已全部跳过"
            )

    # 面积从大到小排序；放不下的种类直接排除
    order = [
        i
        for i, t in enumerate(labels)
        if not oversize[i] and t.quantity > 0
    ]
    order.sort(key=lambda i: -labels[i].width * labels[i].height)
    remaining = {i: labels[i].quantity for i in order}

    pages: List[Page] = []

    def has_remaining() -> bool:
        return any(v > 0 for v in remaining.values())

    def limit_reached() -> bool:
        return max_sheets > 0 and len(pages) >= max_sheets

    while has_remaining() and not limit_reached():
        packer = MaxRects(content_w, content_h, gap_x, gap_y)
        page = Page([], content_w, content_h, 0.0, 0.0)

        # 尽可能往当前页填
        while has_remaining():
            placed_this_round = False
            # 每轮按面积顺序给每种标签尝试放一个，放大件优先
            for i in order:
                if remaining.get(i, 0) <= 0:
                    continue
                t = labels[i]
                outcome = packer.insert(t.width, t.height, allow_rotate)
                if outcome is None:
                    continue
                node, rotated = outcome
                planned[i] += 1
                page.placements.append(
                    Placement(
                        type_index=i,
                        name=t.name,
                        width=t.width,
                        height=t.height,
                        x=node.x,
                        y=node.y,
                        rotated=rotated,
                        sequence=planned[i],
                    )
                )
                remaining[i] -= 1
                placed_this_round = True

            if not placed_this_round:
                break  # 当前页放不下任何剩余标签

        if page.placements:
            pages.append(_finalize_page(page))
        order = [i for i in order if remaining.get(i, 0) > 0]
        if not page.placements:
            break  # 空页说明剩余标签无法再排入（理论上被 oversize 拦截，保险起见）

    for i, t in enumerate(labels):
        if planned[i] < t.quantity and not oversize[i]:
            warnings.append(
                f"标签“{t.name}”需求 {t.quantity} 枚，受最大页数限制仅排入 "
                f"{planned[i]} 枚，剩余 {t.quantity - planned[i]} 枚未排"
            )

    return LayoutResult(
        pages=pages,
        planned=planned,
        requested=requested,
        oversize=oversize,
        warnings=warnings,
    )


def _finalize_page(page: Page) -> Page:
    used = sum(p.width * p.height for p in page.placements)
    area = page.content_width * page.content_height
    page.used_area = used
    page.fill_ratio = used / area if area > 0 else 0.0
    return page


def _fmt(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < EPS else f"{v:.1f}"
