"""Pydantic 模型：拼版请求/响应。"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator


class LabelIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    width: float = Field(..., gt=0, le=2000)
    height: float = Field(..., gt=0, le=2000)
    quantity: int = Field(..., ge=1, le=1_000_000)


class LayoutIn(BaseModel):
    page_width: float = Field(..., gt=0, le=5000)
    page_height: float = Field(..., gt=0, le=5000)
    margin_top: float = Field(0, ge=0, le=500)
    margin_right: float = Field(0, ge=0, le=500)
    margin_bottom: float = Field(0, ge=0, le=500)
    margin_left: float = Field(0, ge=0, le=500)
    gap_x: float = Field(0, ge=0, le=500)
    gap_y: float = Field(0, ge=0, le=500)
    allow_rotate: bool = True
    show_text: bool = True
    crop_marks: bool = True
    max_sheets: int = Field(0, ge=0, le=10000)
    labels: List[LabelIn] = Field(..., min_length=1)

    @field_validator("labels")
    @classmethod
    def _strip_names(cls, v: List[LabelIn]) -> List[LabelIn]:
        for item in v:
            item.name = item.name.strip() or "标签"
        return v

    def validate_margins(self) -> None:
        if self.margin_left + self.margin_right >= self.page_width:
            raise ValueError("左右页边距之和必须小于纸张宽度")
        if self.margin_top + self.margin_bottom >= self.page_height:
            raise ValueError("上下页边距之和必须小于纸张高度")


class DownloadIn(LayoutIn):
    """下载多页合并 SVG 的请求体（与 /api/layout 相同，另加装订方向）。"""

    sheet_gap: float = Field(6.0, ge=0, le=100)
