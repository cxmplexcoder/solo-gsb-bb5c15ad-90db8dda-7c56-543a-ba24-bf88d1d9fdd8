/* 小批量标签拼版工具 —— 前端逻辑（原生 JS，无构建） */
"use strict";

const $ = (id) => document.getElementById(id);

let lastPlan = null;     // 最近一次 /api/layout 返回的拼版结果
let lastParams = null;   // 对应的请求参数
let currentPage = 1;
let rowSeq = 0;

/* ---------------- 标签行 ---------------- */

function addLabelRow(spec) {
  const data = spec || { name: "", width: 60, height: 30, count: 10, allow_rotate: false };
  const row = document.createElement("div");
  row.className = "label-row";
  row.innerHTML = `
    <input type="text" class="l-name" placeholder="标签名称" value="${escapeAttr(data.name)}" />
    <input type="number" class="l-w" value="${data.width}" step="0.5" min="0.1" title="宽 mm" />
    <input type="number" class="l-h" value="${data.height}" step="0.5" min="0.1" title="高 mm" />
    <input type="number" class="l-c" value="${data.count}" step="1" min="1" title="份数" />
    <label class="rot-cell" title="允许旋转 90°">
      <input type="checkbox" class="l-r" ${data.allow_rotate ? "checked" : ""} />旋转
    </label>
    <button type="button" class="del" title="删除">✕</button>
  `;
  row.querySelector(".del").addEventListener("click", () => row.remove());
  $("label-rows").appendChild(row);
}

function escapeAttr(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

/* ---------------- 参数收集 ---------------- */

function num(id) {
  return parseFloat($(id).value);
}

function collectParams() {
  const labels = [...document.querySelectorAll(".label-row")].map((row) => ({
    name: row.querySelector(".l-name").value.trim(),
    width: parseFloat(row.querySelector(".l-w").value),
    height: parseFloat(row.querySelector(".l-h").value),
    count: parseInt(row.querySelector(".l-c").value, 10),
    allow_rotate: row.querySelector(".l-r").checked,
  }));
  return {
    page_width: num("page-width"),
    page_height: num("page-height"),
    margin_top: num("margin-top"),
    margin_right: num("margin-right"),
    margin_bottom: num("margin-bottom"),
    margin_left: num("margin-left"),
    gap_x: num("gap-x"),
    gap_y: num("gap-y"),
    labels,
  };
}

async function fetchSvg(page) {
  const body = {
    page,
    show_margins: $("show-margins").checked,
    show_annotations: $("show-annotations").checked,
    params: lastParams,
  };
  const resp = await fetch("/api/svg", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error((await resp.json()).detail || "SVG 生成失败");
  return resp.text();
}

async function renderPage() {
  if (!lastPlan) return;
  const svg = await fetchSvg(currentPage);
  $("svg-host").innerHTML = svg;
  $("page-info").textContent = `${currentPage} / ${lastPlan.pages.length}`;
  $("prev-page").disabled = currentPage <= 1;
  $("next-page").disabled = currentPage >= lastPlan.pages.length;
}

/* ---------------- 结果汇总 ---------------- */

function renderSummary(plan) {
  const el = $("summary");
  el.classList.remove("empty");
  const allPlaced = plan.total_placed === plan.total_requested;
  let html = `<div class="totals">
      共 <strong>${plan.total_requested}</strong> 个标签，
      排入 <strong class="ok">${plan.total_placed}</strong> 个，
      使用 <strong>${plan.pages.length}</strong> 张纸
      ${allPlaced ? "（全部排入 ✔）" : `，<strong style="color:var(--danger)">${plan.total_requested - plan.total_placed} 个未排入</strong>`}
    </div>
    <table>
      <thead><tr>
        <th>标签</th><th>规格 (mm)</th><th>需求</th><th>排入</th><th>其中旋转</th><th>未排入</th>
      </tr></thead><tbody>`;
  for (const s of plan.summaries) {
    html += `<tr class="${s.unplaced > 0 ? "unplaced" : ""}">
      <td>${escapeHtml(s.name || `#${s.type_index + 1}`)}</td>
      <td>${s.width} × ${s.height}</td>
      <td>${s.requested}</td>
      <td>${s.placed}</td>
      <td>${s.rotated}</td>
      <td>${s.unplaced > 0 ? s.unplaced : "—"}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  if (plan.warnings.length) {
    html += `<div class="warn"><strong>提示：</strong><ul>${
      plan.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")
    }</ul></div>`;
  }
  el.innerHTML = html;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------------- 事件 ---------------- */

$("add-label").addEventListener("click", () => addLabelRow());

$("preset").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const [w, h] = e.target.value.split(",").map(parseFloat);
  $("page-width").value = w;
  $("page-height").value = h;
});

$("params-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  lastParams = collectParams();
  currentPage = 1;
  try {
    const resp = await fetch("/api/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lastParams),
    });
    if (!resp.ok) {
      const detail = (await resp.json()).detail;
      throw new Error(Array.isArray(detail)
        ? detail.map((d) => d.msg).join("；")
        : detail);
    }
    lastPlan = await resp.json();
    renderSummary(lastPlan);
    $("preview-wrap").hidden = false;
    await renderPage();
  } catch (err) {
    lastPlan = null;
    $("preview-wrap").hidden = true;
    $("summary").className = "summary";
    $("summary").innerHTML =
      `<div class="warn"><strong>参数错误：</strong>${escapeHtml(err.message)}</div>`;
  }
});

$("prev-page").addEventListener("click", async () => {
  if (currentPage > 1) { currentPage--; await renderPage(); }
});
$("next-page").addEventListener("click", async () => {
  if (lastPlan && currentPage < lastPlan.pages.length) {
    currentPage++; await renderPage();
  }
});

$("show-margins").addEventListener("change", renderPage);
$("show-annotations").addEventListener("change", renderPage);

function downloadBlob(text, filename, type) {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

$("download-svg").addEventListener("click", async () => {
  const svg = await fetchSvg(currentPage);
  downloadBlob(svg, `labels-page-${currentPage}.svg`, "image/svg+xml");
});

$("download-all").addEventListener("click", async () => {
  for (let p = 1; p <= lastPlan.pages.length; p++) {
    const svg = await fetchSvg(p);
    downloadBlob(svg, `labels-page-${p}.svg`, "image/svg+xml");
    await new Promise((r) => setTimeout(r, 150)); // 避免浏览器拦截批量下载
  }
});

$("print-all").addEventListener("click", async () => {
  const svgs = [];
  for (let p = 1; p <= lastPlan.pages.length; p++) svgs.push(await fetchSvg(p));
  const w = lastPlan.page_width, h = lastPlan.page_height;
  const win = window.open("", "_blank");
  if (!win) { alert("浏览器拦截了打印窗口，请允许弹窗后重试。"); return; }
  win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>打印标签</title>
    <style>
      @page { size: ${w}mm ${h}mm; margin: 0; }
      html,body { margin:0; padding:0; }
      .sheet { width:${w}mm; height:${h}mm; overflow:hidden; page-break-after:always; }
      .sheet:last-child { page-break-after:auto; }
      svg { display:block; width:${w}mm; height:${h}mm; }
    </style></head><body>
    ${svgs.map((s) => `<div class="sheet">${s}</div>`).join("")}
    </body></html>`);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 400);
});

/* ---------------- 初始数据 ---------------- */

addLabelRow({ name: "品名标签", width: 60, height: 30, count: 20, allow_rotate: true });
addLabelRow({ name: "箱贴", width: 100, height: 70, count: 6, allow_rotate: false });
addLabelRow({ name: "小标", width: 40, height: 20, count: 50, allow_rotate: true });
