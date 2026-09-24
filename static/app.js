/* 标签拼版工具前端逻辑（原生 JS，无框架） */
"use strict";

const PRESETS = {
  A4: [210, 297],
  A3: [297, 420],
  A5: [148, 210],
  Letter: [215.9, 279.4],
};
const SCREEN_SCALE = 3.4; // 屏幕预览：1mm = 3.4px（打印时由 CSS 还原为物理毫米）

const $ = (id) => document.getElementById(id);
let lastPayload = null;

/* ---------------- 纸张预设 ---------------- */
function applyPreset() {
  const preset = $("paperPreset").value;
  if (preset === "custom") return;
  let [w, h] = PRESETS[preset];
  if ($("paperOrient").value === "landscape") [w, h] = [h, w];
  $("pageW").value = w;
  $("pageH").value = h;
}

function onManualSize() {
  $("paperPreset").value = "custom";
}

/* ---------------- 标签行 ---------------- */
function addLabelRow(name = "", w = "", h = "", qty = "") {
  const tbody = $("labelRows");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td class="name-cell"><input type="text" class="l-name" maxlength="40"
      placeholder="名称" value="${escapeAttr(name)}"></td>
    <td class="num-cell"><input type="number" class="l-w" min="1" max="2000"
      step="0.1" value="${w}"></td>
    <td class="num-cell"><input type="number" class="l-h" min="1" max="2000"
      step="0.1" value="${h}"></td>
    <td class="num-cell"><input type="number" class="l-q" min="1" max="1000000"
      step="1" value="${qty}"></td>
    <td class="del-cell"><button type="button" class="icon-btn"
      title="删除">✕</button></td>`;
  tr.querySelector(".icon-btn").addEventListener("click", () => {
    if (tbody.children.length > 1) tr.remove();
  });
  tbody.appendChild(tr);
}

function escapeAttr(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

/* ---------------- 收集参数 ---------------- */
function num(id) {
  return parseFloat($(id).value);
}

function buildPayload() {
  const labels = [];
  document.querySelectorAll("#labelRows tr").forEach((tr) => {
    const name = tr.querySelector(".l-name").value.trim() || "标签";
    const w = parseFloat(tr.querySelector(".l-w").value);
    const h = parseFloat(tr.querySelector(".l-h").value);
    const q = parseInt(tr.querySelector(".l-q").value, 10);
    if (w > 0 && h > 0 && q > 0) {
      labels.push({ name, width: w, height: h, quantity: q });
    }
  });
  if (labels.length === 0) {
    throw new Error("请至少填写一行有效的标签（宽、高、份数均需大于 0）");
  }
  return {
    page_width: num("pageW"),
    page_height: num("pageH"),
    margin_top: num("mTop") || 0,
    margin_right: num("mRight") || 0,
    margin_bottom: num("mBottom") || 0,
    margin_left: num("mLeft") || 0,
    gap_x: num("gapX") || 0,
    gap_y: num("gapY") || 0,
    allow_rotate: $("allowRotate").checked,
    show_text: $("showText").checked,
    crop_marks: $("cropMarks").checked,
    max_sheets: parseInt($("maxSheets").value, 10) || 0,
    labels,
  };
}

function showError(msg) {
  const box = $("errorBox");
  box.textContent = msg;
  box.hidden = !msg;
}

function extractError(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d) => d.msg || JSON.stringify(d))
      .join("\n");
  }
  return fallback;
}

/* ---------------- 排版 ---------------- */
async function runLayout() {
  showError("");
  let payload;
  try {
    payload = buildPayload();
  } catch (e) {
    showError(e.message);
    return;
  }
  lastPayload = payload;

  const btn = $("runBtn");
  btn.disabled = true;
  btn.textContent = "排版中…";
  try {
    const resp = await fetch("/api/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
      showError(extractError(data, `排版失败（HTTP ${resp.status}）`));
      return;
    }
    renderResult(data, payload);
  } catch (e) {
    showError("请求失败：" + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "开始排版";
  }
}

function renderResult(data, payload) {
  // 工具栏
  $("toolbar").hidden = false;
  const totalPlaced = data.summary.reduce((s, r) => s + r.placed, 0);
  $("stats").textContent =
    `共 ${data.page_count} 页 · 排入 ${totalPlaced} 枚标签`;

  // 汇总表
  $("summaryWrap").hidden = false;
  const body = $("summaryBody");
  body.innerHTML = "";
  data.summary.forEach((row) => {
    const tr = document.createElement("tr");
    let status;
    if (row.oversize) {
      status = '<span class="tag err">超出页面</span>';
    } else if (row.remaining > 0) {
      status = `<span class="tag warn">缺 ${row.remaining}</span>`;
    } else {
      status = '<span class="tag ok">完成</span>';
    }
    tr.innerHTML = `
      <td><span class="swatch" style="background:${row.color}"></span></td>
      <td>${escapeHtml(row.name)}</td>
      <td>${row.width}×${row.height} mm</td>
      <td>${row.requested}</td>
      <td><strong>${row.placed}</strong> ${status}</td>
      <td>${row.remaining}</td>`;
    body.appendChild(tr);
  });

  const warnUl = $("warnings");
  warnUl.innerHTML = "";
  data.warnings.forEach((w) => {
    const li = document.createElement("li");
    li.textContent = w;
    warnUl.appendChild(li);
  });

  // 页面预览：直接使用后端返回的 SVG（与下载同源同坐标）
  const pages = $("pages");
  pages.innerHTML = "";
  $("emptyHint").hidden = data.page_count > 0;
  data.pages.forEach((svg, i) => {
    const card = document.createElement("div");
    card.className = "page-card";
    const meta = data.page_meta[i];
    card.innerHTML = `
      <div class="caption">
        <span>第 ${i + 1} / ${data.page_count} 页</span>
        <span>${meta.count} 枚</span>
        <span>利用率 ${(meta.fill_ratio * 100).toFixed(1)}%</span>
      </div>
      ${svg}`;
    const svgEl = card.querySelector("svg.sheet");
    // 屏幕预览缩放；打印时由 @media print 还原为物理毫米
    svgEl.style.width = payload.page_width * SCREEN_SCALE + "px";
    svgEl.style.height = "auto";
    pages.appendChild(card);
  });

  // 动态设置打印纸张尺寸，保证浏览器打印按毫米走纸
  setPrintPageSize(payload.page_width, payload.page_height);
}

function setPrintPageSize(w, h) {
  let style = document.getElementById("dynamicPageSize");
  if (!style) {
    style = document.createElement("style");
    style.id = "dynamicPageSize";
    document.head.appendChild(style);
  }
  style.textContent = `@page { size: ${w}mm ${h}mm; margin: 0; }`;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ---------------- 下载 SVG ---------------- */
async function downloadSvg() {
  if (!lastPayload) return;
  showError("");
  try {
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...lastPayload, sheet_gap: 6 }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => null);
      showError(extractError(data, `导出失败（HTTP ${resp.status}）`));
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "labels-imposition.svg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    showError("导出失败：" + e.message);
  }
}

/* ---------------- 初始化 ---------------- */
function init() {
  $("paperPreset").addEventListener("change", applyPreset);
  $("paperOrient").addEventListener("change", applyPreset);
  $("pageW").addEventListener("input", onManualSize);
  $("pageH").addEventListener("input", onManualSize);
  $("addLabel").addEventListener("click", () => addLabelRow("", "", "", ""));
  $("runBtn").addEventListener("click", runLayout);
  $("downloadBtn").addEventListener("click", downloadSvg);
  $("printBtn").addEventListener("click", () => window.print());

  // 默认示例
  addLabelRow("产品标签", 60, 40, 12);
  addLabelRow("条码", 40, 25, 20);
  addLabelRow("圆形贴", 30, 30, 8);
}

document.addEventListener("DOMContentLoaded", init);
