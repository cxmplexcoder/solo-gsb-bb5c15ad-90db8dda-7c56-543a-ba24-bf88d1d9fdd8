"""请求 / 响应数据模型（单位均为毫米）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LabelSpec(BaseModel):
    """一种标签规格及其需要的份数。"""

    name: str = Field("", description="标签名称")
    width: float = Field(..., gt=0, description="标签宽度 mm")
    height: float = Field(..., gt=0, description="标签高度 mm")
    count: int = Field(..., ge=1, description="需要份数")
    allow_rotate: bool = Field(False, description="是否允许旋转 90 度排版")


class LayoutRequest(BaseModel):
    """拼版参数。"""

    page_width: float = Field(..., gt=0, description="纸张宽度 mm")
    page_height: float = Field(..., gt=0, description="纸张高度 mm")
    margin_top: float = Field(0, ge=0)
    margin_right: float = Field(0, ge=0)
    margin_bottom: float = Field(0, ge=0)
    margin_left: float = Field(0, ge=0)
    gap_x: float = Field(0, ge=0, description="水平裁切间距 mm")
    gap_y: float = Field(0, ge=0, description="垂直裁切间距 mm")
    labels: list[LabelSpec] = Field(..., min_length=1)


class PlacedLabel(BaseModel):
    """单个已排入标签（毫米坐标，原点为纸张左上角）。"""

    type_index: int
    name: str
    x: float
    y: float
    width: float
    height: float
    rotated: bool


class PageLayout(BaseModel):
    page: int
    width: float
    height: float
    labels: list[PlacedLabel]


class LabelSummary(BaseModel):
    type_index: int
    name: str
    width: float
    height: float
    requested: int
    placed: int
    rotated: int
    unplaced: int


class LayoutResponse(BaseModel):
    pages: list[PageLayout]
    summaries: list[LabelSummary]
    total_requested: int
    total_placed: int
    warnings: list[str]
    # 回显参数，供绘制 / 导出使用，保证预览与导出同源
    page_width: float
    page_height: float
    margin_top: float
    margin_right: float
    margin_bottom: float
    margin_left: float
    gap_x: float
    gap_y: float


class SvgRequest(BaseModel):
    """SVG 导出请求：参数与 /api/layout 完全一致，附带页码与显示开关。"""

    page: int = Field(1, ge=1)
    show_margins: bool = True
    show_annotations: bool = True
    params: LayoutRequest


class SvgResponse(BaseModel):
    svg: str
