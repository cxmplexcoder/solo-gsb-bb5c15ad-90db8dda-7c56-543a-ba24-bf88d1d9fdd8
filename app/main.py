"""FastAPI 入口：静态页面 + 拼版 API。

- GET  /                  前端单页
- POST /api/layout        排样，返回每页 SVG（预览）与汇总数据
- POST /api/download      同样的参数，返回多页合并 SVG 文件
- GET  /api/health        健康检查
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .layout import LabelType, layout_labels
from .schemas import DownloadIn, LayoutIn
from .svg import color_for, render_multi_page_svg, render_page_svg

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="标签拼版工具", version="1.0.0")


@app.on_event("startup")
def _init() -> None:
    """启动时初始化：数据目录（当前无持久化需求，仅确保目录可用）。"""
    data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def _compute_result(payload: LayoutIn):
    payload.validate_margins()
    labels = [
        LabelType(name=t.name, width=t.width, height=t.height,
                  quantity=t.quantity)
        for t in payload.labels
    ]
    return layout_labels(
        labels,
        page_width=payload.page_width,
        page_height=payload.page_height,
        margin_top=payload.margin_top,
        margin_right=payload.margin_right,
        margin_bottom=payload.margin_bottom,
        margin_left=payload.margin_left,
        gap_x=payload.gap_x,
        gap_y=payload.gap_y,
        allow_rotate=payload.allow_rotate,
        max_sheets=payload.max_sheets,
    )


def _run_layout(payload: LayoutIn) -> Dict[str, Any]:
    result = _compute_result(payload)

    pages_svg: List[str] = []
    pages_meta = []
    total = len(result.pages)
    for idx, page in enumerate(result.pages):
        pages_svg.append(
            render_page_svg(
                page,
                payload.page_width,
                payload.page_height,
                payload.margin_top,
                payload.margin_right,
                payload.margin_bottom,
                payload.margin_left,
                show_text=payload.show_text,
                crop_marks=payload.crop_marks,
                page_no=idx + 1,
                page_total=total,
            )
        )
        pages_meta.append(
            {
                "count": len(page.placements),
                "fill_ratio": round(page.fill_ratio, 4),
            }
        )

    summary = []
    for i, t in enumerate(payload.labels):
        summary.append(
            {
                "name": t.name,
                "width": t.width,
                "height": t.height,
                "requested": t.quantity,
                "placed": result.planned[i],
                "remaining": max(0, t.quantity - result.planned[i]),
                "oversize": result.oversize[i],
                "color": color_for(i),
            }
        )

    return {
        "pages": pages_svg,
        "page_count": total,
        "page_meta": pages_meta,
        "summary": summary,
        "warnings": result.warnings,
        "page_width": payload.page_width,
        "page_height": payload.page_height,
    }


@app.post("/api/layout")
def api_layout(payload: LayoutIn) -> Dict[str, Any]:
    try:
        return _run_layout(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/download")
def api_download(payload: DownloadIn) -> Response:
    try:
        result = _compute_result(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not result.pages:
        raise HTTPException(status_code=400, detail="没有可排入的标签")

    svg = render_multi_page_svg(
        result,
        payload.page_width,
        payload.page_height,
        payload.margin_top,
        payload.margin_right,
        payload.margin_bottom,
        payload.margin_left,
        show_text=payload.show_text,
        crop_marks=payload.crop_marks,
        sheet_gap=payload.sheet_gap,
    )
    filename = "labels-imposition.svg"
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# 静态资源（/static/...）与首页必须挂在路由之后不冲突
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
