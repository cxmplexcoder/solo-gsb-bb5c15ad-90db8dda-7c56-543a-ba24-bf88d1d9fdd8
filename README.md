# 标签拼版工具（Label Imposition）

小批量标签自动拼版的 Web 工具。输入纸张尺寸、页边距、多种标签的宽高与份数、
裁切间距以及是否允许旋转，工具使用 **MaxRects（Best Short Side Fit）** 算法在
每张纸上自动安排互不重叠的位置；一页放不下时自动续页，并显示**每种标签实际排入
的数量**（含未排/超页提示）。

预览与下载/打印共用同一套**毫米坐标**的 SVG 渲染函数，因此屏幕所见即导出所得，
页边距、裁切间距在两种产物中严格一致。

技术栈：**Python 3.11 + FastAPI** 后端，**原生 HTML / CSS / JavaScript** 前端
（无构建步骤、无 npm 依赖）。

---

## 一条命令启动

```bash
docker compose up --build
```

启动后浏览器访问：

> **http://localhost:8000**

停止：

```bash
docker compose down
```

> 端口可在 `docker-compose.yml` 的 `ports` 中修改（默认宿主机 `8000`）。
> 容器启动时会自动校验/安装依赖并初始化数据目录（`docker/entrypoint.sh`）。

---

## 功能

- **纸张**：A4 / A3 / A5 / Letter 预设，或自定义任意毫米尺寸，支持纵/横向
- **页边距**：上、下、左、右分别设置（mm）
- **标签规格**：可添加任意多种规格，每种包含名称、宽、高、份数
- **裁切间距**：横向 / 纵向间距独立设置（相邻标签之间只计一次，不会重复叠加）
- **自动旋转**：可选允许标签旋转 90° 以提高填充率（旋转标签在图中带 ↻ 标识）
- **自动续页**：单页放不下时自动新增纸张，直到排完或达到最大页数
- **排入统计**：表格显示每种标签的需求数、实际排入数、未排数与超页状态
- **毫米坐标 SVG**：`width="210mm" viewBox="0 0 210 297"`，预览与导出同源
- **裁切标记**：每个标签四角自动生成 L 形裁切线（贴近纸边的臂会自动收缩）
- **下载 / 打印**：一键下载多页合并 SVG；打印时按物理毫米走纸（`@page size`）
- 可选**最大页数**上限，超出部分给出告警而不是无限生成

---

## 目录结构

```
.
├── app/
│   ├── main.py          # FastAPI 路由：/api/layout、/api/download、/
│   ├── layout.py        # MaxRects 排样核心（纯标准库，单位 mm）
│   ├── svg.py           # SVG 渲染（预览与下载共用）
│   └── schemas.py       # 请求参数校验（Pydantic）
├── static/
│   ├── index.html       # 单页前端
│   ├── style.css
│   └── app.js           # 参数收集、预览渲染、下载/打印
├── tests/
│   ├── test_layout.py   # 排样算法测试（不重叠/不出界/间距/续页/上限）
│   └── test_svg.py      # SVG 坐标一致性测试
├── docker/
│   └── entrypoint.sh    # 启动时校验依赖 + 初始化数据目录
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/` | 前端页面 |
| POST | `/api/layout` | 排样，返回每页 SVG 字符串、页数、每页利用率、每种标签排入数量、告警 |
| POST | `/api/download` | 相同参数，返回多页合并的 `image/svg+xml` 文件（附件下载） |
| GET  | `/api/health` | 健康检查 |

请求体示例：

```json
{
  "page_width": 210,
  "page_height": 297,
  "margin_top": 5,
  "margin_right": 5,
  "margin_bottom": 5,
  "margin_left": 5,
  "gap_x": 2,
  "gap_y": 2,
  "allow_rotate": true,
  "show_text": true,
  "crop_marks": true,
  "max_sheets": 0,
  "labels": [
    {"name": "产品标签", "width": 60, "height": 40, "quantity": 12},
    {"name": "条码",     "width": 40, "height": 25, "quantity": 20}
  ]
}
```

所有尺寸单位均为毫米（mm）。`max_sheets=0` 表示不限页数。

---

## 本地开发（不使用 Docker）

需要 Python 3.11+：

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000

运行测试（测试仅使用 Python 标准库，无需安装依赖）：

```bash
python tests/test_layout.py
python tests/test_svg.py
```

---

## 算法与坐标约定

- 排样在「可打印区」内进行，尺寸为
  `纸宽 − 左 − 右边距` × `纸高 − 上 − 下边距`。
- 每个标签按 `(标签宽 + gap_x) × (标签高 + gap_y)` 的槽位参与排样，内容位于
  槽位左上角。这样相邻标签之间恰好留一个间距，最右一列/最下一行也不会把间距
  重复叠加到纸边——标签内容严格停在页边距线上。
- 允许旋转时，同一标签会分别以原方向与 90° 方向参与 BSSF 打分，取更优者。
- 排样顺序按单标签面积从大到小（大件先排是排样问题的常规启发式）。
- 预览接口返回的每个 `<svg>` 与下载文件中对应页面来自 `svg.py` 的**同一函数**，
  差别仅是下载文件把多页包进根 `<svg>` 的 `<g transform="translate(...)">`，
  各页内部坐标完全相同。

## 打印说明

SVG 的 `width/height` 使用物理毫米单位；前端打印样式会把 `@page` 设置为输入的
纸张尺寸且零边距，每一页对应一张纸（`page-break-after: always`）。在浏览器打印
对话框中选择「实际大小 / 100%」、关闭页眉页脚即可按毫米输出；也可以直接下载 SVG
后使用专业 RIP / 矢量软件打印。
