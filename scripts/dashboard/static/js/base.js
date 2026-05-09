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
