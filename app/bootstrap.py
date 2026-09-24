"""启动初始化：校验配置、自检关键模块可导入。

容器启动时由 entrypoint.sh 调用（python -m app.bootstrap）。
无数据库等外部依赖；这里执行运行环境自检并输出启动横幅。
"""

from __future__ import annotations

import sys


def main() -> int:
    print("[bootstrap] 小批量标签拼版工具 —— 初始化开始")

    # 依赖与核心模块自检
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        print(f"[bootstrap] 依赖缺失: {exc}", file=sys.stderr)
        return 1

    from .layout import compute_layout
    from .models import LayoutRequest, LabelSpec
    from .svg import build_svg

    # 用一个最小样例冒烟测试排版 + SVG 管线
    smoke = LayoutRequest(
        page_width=210, page_height=297,
        margin_top=8, margin_right=8, margin_bottom=8, margin_left=8,
        gap_x=2, gap_y=2,
        labels=[LabelSpec(width=60, height=30, count=4, allow_rotate=True)],
    )
    plan = compute_layout(smoke)
    build_svg(plan, 1)
    assert plan.total_placed == 4

    print(f"[bootstrap] 自检通过（FastAPI {fastapi.__version__}, "
          f"Pydantic {pydantic.VERSION}）")
    print("[bootstrap] 初始化完成，等待 uvicorn 启动 ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
