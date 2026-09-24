"""SVG 渲染：预览与下载共用同一套毫米坐标。

约定：
- SVG viewBox/width/height 均使用毫米（width="210mm" viewBox="0 0 210 297"），
  屏幕预览与打印导出出自同一函数，边距/间距天然一致。
- 纸张原点在左上角，y 轴向下；标签坐标先加上页边距再绘制。
"""

from __future__ import annotations

from html import escape
from typing import List

from .layout import LayoutResult, Page, Placement

# 按标签种类循环的填充色
PALETTE = [
    "#cfe8ff", "#d9f2d9", "#ffe8c2", "#f5d6d6",
    "#e6d9f5", "#d6f5f2", "#f5f0ce", "#f0d9e8",
]

CROP_LEN = 2.0     # 裁切线默认长度（mm）
CROP_GAP = 0.3     # 裁切线距标签边缘的间隙（mm）
CROP_COLOR = "#444444"
CROP_STROKE = 0.15


def color_for(type_index: int) -> str:
    return PALETTE[type_index % len(PALETTE)]


def _f(v: float) -> str:
    """毫米数值格式化：保留最多 3 位小数，去掉多余的 0。"""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def render_page_svg(
    page: Page,
    page_width: float,
    page_height: float,
    margin_top: float,
    margin_right: float,
    margin_bottom: float,
    margin_left: float,
    *,
    show_text: bool = True,
    crop_marks: bool = True,
    page_no: int = 1,
    page_total: int = 1,
    standalone: bool = True,
) -> str:
    """渲染单张纸。

    standalone=True 返回完整独立可用的 <svg> 文档（预览/单页下载）；
    standalone=False 仅返回内部元素，供多页文件包进 <g>（避免嵌套 svg）。
    """
    parts: List[str] = []
    if standalone:
        parts.append(
            f'<svg class="sheet" xmlns="http://www.w3.org/2000/svg" '
            f'width="{_f(page_width)}mm" height="{_f(page_height)}mm" '
            f'viewBox="0 0 {_f(page_width)} {_f(page_height)}" '
            f'data-page="{page_no}">'
        )
    # 纸面
    parts.append(
        f'<rect x="0" y="0" width="{_f(page_width)}" '
        f'height="{_f(page_height)}" fill="#ffffff" stroke="#9aa4b2" '
        f'stroke-width="0.25"/>'
    )
    # 可打印区参考线（页边距）
    cx = margin_left
    cy = margin_top
    parts.append(
        f'<rect x="{_f(cx)}" y="{_f(cy)}" '
        f'width="{_f(page.content_width)}" height="{_f(page.content_height)}" '
        f'fill="none" stroke="#b9c2cf" stroke-width="0.12" '
        f'stroke-dasharray="1.2 1.2"/>'
    )

    for p in page.placements:
        _render_label(parts, p, margin_left, margin_top, page_width,
                      page_height, show_text, crop_marks)

    # 页脚页码（页面底边居中），不侵入标签区域
    parts.append(
        f'<text x="{_f(page_width / 2)}" '
        f'y="{_f(page_height - margin_bottom / 2 + 1.2)}" '
        f'text-anchor="middle" font-family="Arial, sans-serif" '
        f'font-size="2.6" fill="#8a93a3">第 {page_no} / {page_total} 页</text>'
    )

    if standalone:
        parts.append("</svg>")
    return "".join(parts)


def _render_label(
    parts: List[str],
    p: Placement,
    margin_left: float,
    margin_top: float,
    page_width: float,
    page_height: float,
    show_text: bool,
    crop_marks: bool,
) -> None:
    fill = color_for(p.type_index)
    x = margin_left + p.x
    y = margin_top + p.y
    # 旋转标签：内容整体转 90°，绘制矩形宽高互换，与排样槽位一致
    w, h = (p.height, p.width) if p.rotated else (p.width, p.height)

    parts.append(
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" '
        f'rx="0.4" fill="{fill}" stroke="#5b6775" stroke-width="0.18"/>'
    )

    if show_text:
        _render_text(parts, p, x, y, w, h)

    if crop_marks:
        _render_crops(parts, x, y, w, h, page_width, page_height)


def _render_text(parts: List[str], p: Placement, x: float, y: float,
                 w: float, h: float) -> None:
    """标签内文字：名称 + 序号。

    调用时 w/h 已是绘制矩形的宽高（旋转标签已互换）。
    文字始终水平排版两行；旋转标签整体绕矩形中心转 90°。
    """
    display_name = ("↻ " + p.name) if p.rotated else p.name
    # 文字始终水平两行排版；旋转标签的"阅读框"为原始宽高
    read_w, read_h = p.width, p.height
    font = min(5.5, read_h * 0.30,
               read_w / max(6.0, len(display_name) * 1.0))
    font = max(2.4, min(font, read_w * 0.6))
    if font < 2.6 or read_w < 7.0 or read_h < 7.0:
        return  # 太小就不画文字，避免糊成一团

    cx, cy = x + w / 2, y + h / 2
    line1 = escape(display_name)
    line2 = escape(
        f"#{p.sequence}  {_f(p.width)}×{_f(p.height)}mm"
        if not p.rotated else f"#{p.sequence}"
    )

    open_tf = ""
    close_tf = ""
    if p.rotated:
        # 绕矩形中心旋转：旋转后水平文字落到竖直矩形内
        open_tf = f'<g transform="rotate(90 {_f(cx)} {_f(cy)})">'
        close_tf = "</g>"

    parts.append(open_tf)
    parts.append(
        f'<text x="{_f(cx)}" y="{_f(cy)}" text-anchor="middle" '
        f'font-family="Arial, \'Noto Sans CJK SC\', sans-serif" '
        f'fill="#2f3640">'
        f'<tspan x="{_f(cx)}" dy="-0.35em" font-size="{_f(font)}">'
        f'{line1}</tspan>'
        f'<tspan x="{_f(cx)}" dy="1.25em" font-size="{_f(font * 0.72)}" '
        f'fill="#5b6775">{line2}</tspan></text>'
    )
    parts.append(close_tf)


def _render_crops(parts: List[str], x: float, y: float, w: float, h: float,
                  page_width: float, page_height: float) -> None:
    """在标签四角画向外的 L 形裁切标记；越出纸张的臂自动缩短/放弃。

    每条臂最大长度 CROP_LEN，起点距标签边 CROP_GAP。
    """
    arms: List[tuple] = []
    # (起点x, 起点y, 终点x, 终点y)
    corners = [
        (x - CROP_GAP, y - CROP_GAP, -1, -1),                    # 左上
        (x + w + CROP_GAP, y - CROP_GAP, 1, -1),                 # 右上
        (x - CROP_GAP, y + h + CROP_GAP, -1, 1),                 # 左下
        (x + w + CROP_GAP, y + h + CROP_GAP, 1, 1),              # 右下
    ]
    for cx, cy, dx, dy in corners:
        # 水平臂（沿 x 方向）
        hlen = min(CROP_LEN, max(0.0, cx if dx < 0 else page_width - cx))
        if hlen >= 0.6:
            arms.append((cx, cy, cx + dx * hlen, cy))
        # 垂直臂（沿 y 方向）
        vlen = min(CROP_LEN, max(0.0, cy if dy < 0 else page_height - cy))
        if vlen >= 0.6:
            arms.append((cx, cy, cx, cy + dy * vlen))

    if not arms:
        return
    group = (
        f'<g stroke="{CROP_COLOR}" stroke-width="{CROP_STROKE}" '
        f'stroke-linecap="round">'
    )
    for x1, y1, x2, y2 in arms:
        group += (
            f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" '
            f'y2="{_f(y2)}"/>'
        )
    group += "</g>"
    parts.append(group)


def render_multi_page_svg(
    result: LayoutResult,
    page_width: float,
    page_height: float,
    margin_top: float,
    margin_right: float,
    margin_bottom: float,
    margin_left: float,
    *,
    show_text: bool = True,
    crop_marks: bool = True,
    sheet_gap: float = 6.0,
) -> str:
    """把多张纸纵向拼成一个可下载/打印的 SVG 文件。

    每张纸宽 page_width，相邻纸之间留 sheet_gap mm 空白；
    各页内容与单页预览来自同一个 render_page_svg 调用。
    """
    n = max(1, len(result.pages))
    total_h = n * page_height + (n - 1) * sheet_gap
    parts: List[str] = [
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_f(page_width)}mm" height="{_f(total_h)}mm" '
        f'viewBox="0 0 {_f(page_width)} {_f(total_h)}">'
    ]
    for idx, page in enumerate(result.pages):
        offset_y = idx * (page_height + sheet_gap)
        parts.append(f'<g transform="translate(0 {_f(offset_y)})">')
        parts.append(
            render_page_svg(
                page,
                page_width, page_height,
                margin_top, margin_right, margin_bottom, margin_left,
                show_text=show_text,
                crop_marks=crop_marks,
                page_no=idx + 1,
                page_total=n,
                standalone=False,
            )
        )
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)
