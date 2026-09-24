# 小批量标签拼版 Web 工具

输入纸张尺寸、页边距、多种标签的宽高与份数、裁切间距及是否允许旋转，
自动在每张纸上安排**互不重叠**的位置；放不下自动续页，并显示每种标签
实际排入数量。预览与可下载打印的 SVG 使用**同一套毫米坐标**，页边距与
间距在导出中完全一致。

技术栈：Python 3.11 + FastAPI + 原生 HTML / CSS / JavaScript（无前端构建）。

## 一条命令启动

```bash
docker compose up --build
```

启动后浏览器访问：

- **http://localhost:8000**

停止：`Ctrl+C`，或在另一个终端执行 `docker compose down`。

> 容器启动时会自动执行：安装依赖 → 初始化自检（排版与 SVG 生成冒烟测试）
> → 启动 uvicorn。

## 功能说明

- **纸张**：内置 A4 / A5 / Letter 纵横预设，也可自定义任意毫米尺寸。
- **页边距**：上 / 右 / 下 / 左独立设置。
- **裁切间距**：水平、垂直分别设置；间距只出现在相邻标签之间，
  纸边不留多余半格。
- **多种标签**：任意行数，每行设置名称、宽 (mm)、高 (mm)、份数、
  是否允许旋转 90°。
- **自动排版**：天际线（skyline）左下角装箱，标签位置互不重叠；
  当前页放不下自动续页；允许旋转时会尝试 90° 方向。
- **排入统计**：表格列出每种标签的需求数、实际排入数、旋转数、未排入数；
  单张标签超过可排区域时给出明确提示。
- **预览 / 导出同源**：浏览器预览和下载的 SVG 都由后端
  `POST /api/svg` 基于同一份排版结果生成，单位均为毫米。
- **导出**：支持「下载本页 SVG」「下载全部页」，以及按纸张精确尺寸
  排版的「打印全部页」（`@page size` 等于纸张毫米尺寸，无边距）。

## 接口

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/health` | 健康检查 |
| POST | `/api/layout` | 提交参数，返回分页排版结果（毫米坐标） |
| POST | `/api/svg` | 提交参数 + 页码 + 显示开关，返回该页 SVG |

`/api/svg` 在服务端重新计算同一份排版，保证导出坐标与预览一致。
API 文档（Swagger）：http://localhost:8000/docs

### 请求示例

```json
{
  "page_width": 210,
  "page_height": 297,
  "margin_top": 8,
  "margin_right": 8,
  "margin_bottom": 8,
  "margin_left": 8,
  "gap_x": 2,
  "gap_y": 2,
  "labels": [
    {"name": "品名标签", "width": 60, "height": 30, "count": 20, "allow_rotate": true},
    {"name": "箱贴", "width": 100, "height": 70, "count": 6, "allow_rotate": false}
  ]
}
```

## 本地开发（不使用 Docker）

```bash
pip install -r requirements.txt
python -m app.bootstrap          # 可选：初始化自检
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 目录结构

```
.
├── app/
│   ├── main.py        # FastAPI 路由
│   ├── models.py      # Pydantic 请求/响应模型
│   ├── layout.py      # 天际线拼版算法
│   ├── svg.py         # SVG 生成（预览与导出共用）
│   └── bootstrap.py   # 启动初始化自检
├── static/
│   ├── index.html     # 单页界面
│   ├── style.css
│   └── app.js
├── docker/entrypoint.sh
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
