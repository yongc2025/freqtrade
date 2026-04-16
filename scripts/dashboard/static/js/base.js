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

document.addEventListener("DOMContentLoaded", () => {
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
