/**
 * Base utility functions for FreqTrade Dashboard
 */

const DashState = {
  currentScanData: [],
  currentTradesData: [],
  sortKey: "volume_rank_3d",
  sortAsc: true,
  partialsLoaded: {},
  loadedPages: {
    scan: false,
    trades: false,
    report: false,
    compare: false,
  },
};

// --- Utilities ---
function fmtN(v, d = 2) {
  if (v === null || v === undefined) return "-";
  return Number(v).toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtPct(v, d = 2) {
  if (v === null || v === undefined) return "-";
  const num = Number(v);
  const cls = num >= 0 ? "profit-up" : "profit-down";
  return `<span class="${cls}">${num >= 0 ? "+" : ""}${num.toFixed(d)}%</span>`;
}

function setStatus(id, type, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text ?? "-";

  const colorMap = {
    idle: "secondary",
    info: "info",
    running: "warning",
    ok: "success",
    error: "danger",
  };
  const color = colorMap[type] || type || "secondary";
  if (id === "sp-report") {
    el.className = `status-chip-text text-${color}`;
    return;
  }
  el.className = `small text-${color}`;
}

async function ensurePageMarkup(pageId) {
  const pageEl = document.getElementById("page-" + pageId);
  const viewName = pageEl?.dataset?.view;
  if (!pageEl || !viewName || DashState.partialsLoaded[pageId]) return;

  pageEl.innerHTML =
    '<div class="card border-0 shadow-sm"><div class="card-body text-secondary">页面加载中...</div></div>';

  try {
    const response = await fetch(`/views/${viewName}.html`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Failed to load view: ${viewName}`);
    }

    pageEl.innerHTML = await response.text();
    DashState.partialsLoaded[pageId] = true;
  } catch (error) {
    console.error(error);
    pageEl.innerHTML =
      '<div class="card border-0 shadow-sm"><div class="card-body text-danger">页面片段加载失败，请刷新页面重试。</div></div>';
  }
}

function ensurePageLoaded(pageId) {
  if (DashState.loadedPages[pageId]) return;

  if (pageId === "scan" && typeof loadScanData === "function") {
    loadScanData();
  }
  if (pageId === "trades") {
    if (typeof initTradeFilters === "function") initTradeFilters();
    if (typeof loadTrades === "function") loadTrades();
  }
  if (pageId === "report" && typeof loadReportData === "function") {
    loadReportData();
  }
  if (pageId === "compare" && typeof loadCompareData === "function") {
    loadCompareData();
  }

  DashState.loadedPages[pageId] = true;
}

async function showPage(pageId, linkEl) {
  await ensurePageMarkup(pageId);

  document.querySelectorAll(".page").forEach((p) => {
    p.classList.remove("active");
  });

  const pageEl = document.getElementById("page-" + pageId);
  if (pageEl) {
    pageEl.classList.add("active");
  }

  document
    .querySelectorAll(".nav-link")
    .forEach((l) => l.classList.remove("active"));
  const activeLink =
    linkEl || document.querySelector(`.nav-link[data-page="${pageId}"]`);
  if (activeLink) activeLink.classList.add("active");

  ensurePageLoaded(pageId);

  if (pageId === "compare" && typeof loadCompareData === "function") {
    loadCompareData();
  }
}

async function initDatabaseSelector() {
  const selector = document.getElementById("db-selector");
  if (!selector) return;

  try {
    const listResp = await fetch("/api/config/databases");
    const listData = await listResp.json();
    const currentResp = await fetch("/api/config/current-db");
    const currentData = await currentResp.json();

    selector.innerHTML = "";
    listData.databases.forEach((db) => {
      const option = document.createElement("option");
      option.value = db;
      option.textContent = db;
      option.selected = db === currentData.current_db;
      selector.appendChild(option);
    });
    // 金额输入框保持 HTML 默认值，由用户自行调整
  } catch (error) {
    console.error("Failed to init database selector:", error);
    selector.innerHTML = '<option value="">加载失败</option>';
  }
}

function clearAllPageData() {
  // --- 选币扫描 ---
  const scanTbody = document.getElementById("scan-tbody");
  if (scanTbody) scanTbody.innerHTML = "";
  ["sp-scan", "scan-time", "scan-count"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "等待刷新";
  });

  // --- 历史交易 ---
  const tradesTbody = document.getElementById("trades-tbody");
  if (tradesTbody) tradesTbody.innerHTML = "";
  ["ts-total", "ts-pnl", "ts-wr", "ts-avg"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "-";
  });
  ["trade-count"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "0 笔";
  });

  // --- 实盘报告 ---
  [
    "report-kpi-trades", "report-kpi-pnl", "report-kpi-return",
    "report-kpi-winrate", "report-kpi-sharpe", "report-kpi-pf",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el) { el.textContent = "-"; el.className = "value"; }
  });
  const mainMeta = document.getElementById("report-main-meta");
  if (mainMeta) mainMeta.textContent = "实盘运行时间：等待生成实盘报告";
  const warningEl = document.getElementById("report-warning");
  if (warningEl) { warningEl.textContent = ""; warningEl.classList.add("d-none"); }

  // 隐藏日志卡片
  const logWidget = document.getElementById("report-log-widget");
  if (logWidget) logWidget.style.display = "none";

  // 清空表格
  [
    "report-summary-core-body", "report-summary-risk-body",
    "report-pair-body", "report-open-body",
    "report-enter-tag-body", "report-exit-reason-body", "report-mix-tag-body",
  ].forEach((id) => {
    const tbody = document.getElementById(id);
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-center py-3 text-muted">等待生成报告</td></tr>';
  });

  // 清空结构归因
  [
    "report-snap-direction-count", "report-snap-direction-profit-pct",
    "report-snap-direction-profit-abs", "report-snap-avg-stake",
    "report-snap-best-pair", "report-snap-worst-pair", "report-snap-best-worst-trade",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el) { el.textContent = "-"; el.className = "report-snapshot-value"; }
  });

  // 权益曲线图 — 不清除容器（echarts 实例在 report.js 闭包中，此处无法 dispose）
  // 由 renderEquityChart 自行处理：用 setOption(notMerge) 覆盖旧数据
  ["report-equity-current", "report-equity-peak"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "-";
  });
  const ddEl = document.getElementById("report-equity-drawdown");
  if (ddEl) { ddEl.textContent = "-"; ddEl.className = "report-equity-value"; }
  const eqMeta = document.getElementById("report-equity-meta");
  if (eqMeta) eqMeta.textContent = "等待生成资金曲线";
}

async function switchDatabase(dbName) {
  if (!dbName) return;
  const balanceInput = document.getElementById("balance-input");
  const balance = balanceInput ? balanceInput.value : null;

  try {
    let url = `/api/config/switch-db?db_name=${encodeURIComponent(dbName)}`;
    // 只传 db_name，不传 starting_balance — 金额由用户自行决定
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) {
      const err = await response.json();
      alert(`切换失败: ${err.detail}`);
      return;
    }

    const result = await response.json();
    console.log(`[DB Switch] ${result.message}`);

    // 重置页面加载标记，让下次进入页面时重新加载数据
    Object.keys(DashState.loadedPages).forEach((key) => {
      DashState.loadedPages[key] = false;
    });

    const activePage =
      document.querySelector(".page.active")?.id.replace("page-", "") ||
      "scan";

    // 清空所有页面的旧数据，避免用户误以为是新数据库的结果
    clearAllPageData();

    // 非报告页面正常刷新数据
    if (activePage === "scan" && typeof loadScanData === "function") {
      loadScanData();
    }
    if (activePage === "trades" && typeof loadTrades === "function") {
      loadTrades();
    }
    if (activePage === "compare" && typeof loadCompareData === "function") {
      loadCompareData();
    }

    // 报告页面：只提示切换成功，不自动跑分析
    if (activePage === "report") {
      const statusEl = document.getElementById("sp-report");
      if (statusEl) {
        statusEl.textContent = "已切换";
        statusEl.className = "status-chip-text text-info";
      }
      const logWidget = document.getElementById("report-log-widget");
      const logBox = document.getElementById("report-grid-log-box");
      if (logWidget) logWidget.style.display = "";
      if (logBox) {
        logBox.textContent =
          `✅ 已切换数据库: ${dbName}\n` +
          `💰 当前金额: ${balanceInput ? balanceInput.value : "-"} USDT\n\n` +
          `请确认金额无误后，点击「生成报告」开始分析。`;
      }
    }

    DashState.loadedPages[activePage] = true;
  } catch (error) {
    console.error("Switch database error:", error);
    alert("切换数据库请求失败");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initDatabaseSelector();
  showPage("scan", document.querySelector('.nav-link[data-page="scan"]'));

  ["report", "compare"].forEach((pageId) => {
    ensurePageMarkup(pageId).catch((error) => console.error(error));
  });
});

// Global Exports for modular use
window.fmtN = fmtN;
window.fmtPct = fmtPct;
window.setStatus = setStatus;
window.showPage = showPage;
window.ensurePageLoaded = ensurePageLoaded;
window.DashState = DashState;
window.switchDatabase = switchDatabase;
