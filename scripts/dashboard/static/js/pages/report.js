/**
 * Live Analysis Report Page Logic
 */

(function () {
  let _reportPoll = null;
  let _equityChart = null;
  let _reportGrid = null;
  let _compareGrid = null;
  let _equityResizeBound = false;
  let _reportGridRefreshTimer = null;
  let _compareGridRefreshTimer = null;
  const REPORT_LAYOUT_KEY = "freqtrade-dashboard-report-layout-v1";
  const COMPARE_LAYOUT_KEY = "freqtrade-dashboard-compare-layout-v2";
  const REPORT_DEFAULT_LAYOUT = [
    { id: "report-kpis", x: 0, y: 0, w: 12, h: 2 },
    { id: "report-equity", x: 0, y: 2, w: 12, h: 5 },
    { id: "report-summary-core", x: 0, y: 7, w: 4, h: 4 },
    { id: "report-summary-risk", x: 4, y: 7, w: 4, h: 4 },
    { id: "report-structure", x: 8, y: 7, w: 4, h: 4 },
    { id: "report-pair", x: 0, y: 11, w: 12, h: 5 },
    { id: "report-open", x: 0, y: 16, w: 6, h: 5 },
    { id: "report-enter", x: 6, y: 16, w: 6, h: 5 },
    { id: "report-exit", x: 0, y: 21, w: 6, h: 5 },
    { id: "report-mix", x: 6, y: 21, w: 6, h: 5 },
    { id: "report-log", x: 0, y: 26, w: 12, h: 3 },
  ];
  const COMPARE_DEFAULT_LAYOUT = [
    { id: "compare-status-card", x: 0, y: 0, w: 4, h: 4 },
    { id: "compare-diagnosis-card", x: 4, y: 0, w: 8, h: 4 },
    { id: "compare-overview", x: 0, y: 4, w: 12, h: 3 },
    { id: "compare-filters", x: 0, y: 7, w: 7, h: 4 },
    { id: "compare-filter-summary", x: 7, y: 7, w: 5, h: 4 },
    { id: "compare-breakdown", x: 0, y: 11, w: 12, h: 5 },
    { id: "compare-contrib", x: 0, y: 16, w: 5, h: 5 },
    { id: "compare-clusters", x: 5, y: 16, w: 7, h: 5 },
    { id: "compare-metrics", x: 0, y: 21, w: 12, h: 5 },
    { id: "compare-matched", x: 0, y: 26, w: 12, h: 7 },
    { id: "compare-anomalies", x: 0, y: 33, w: 12, h: 7 },
    { id: "compare-bt-only", x: 0, y: 40, w: 6, h: 5 },
    { id: "compare-live-only", x: 6, y: 40, w: 6, h: 5 },
  ];
  const REPORT_SECTION_STATE = {
    pair: { page: 1, pageSize: 5, expanded: false },
    open: { page: 1, pageSize: 5, expanded: false },
    enterTag: { page: 1, pageSize: 5, expanded: false },
    exitReason: { page: 1, pageSize: 5, expanded: false },
    mixTag: { page: 1, pageSize: 5, expanded: false },
  };
  const REPORT_SECTION_DATA = {
    pair: [],
    open: [],
    enterTag: [],
    exitReason: [],
    mixTag: [],
  };
  const COMPARE_STATE = {
    raw: null,
    groupBy: "pair",
    limits: {
      breakdown: 20,
      matched: 20,
      anomalies: 20,
      btOnly: 20,
      liveOnly: 20,
    },
    filters: {
      pair: "",
      enterTag: "",
      side: "",
      bucket: "",
      exitReason: "",
    },
  };
  const COMPARE_FIELD_HELP = {
    匹配率:
      "已匹配交易数占回测交易总数的比例。越高说明实盘执行结果越能复现回测信号。",
    回测漏单率:
      "回测里出现、但实盘里没有找到对应交易的比例。通常对应漏单、未成交、过滤器变化或风控拦截。",
    实盘额外单率:
      "实盘里出现、但回测里没有对应交易的比例。通常对应配置差异、pairlist 差异、重复触发或数据源偏移。",
    平均入场延迟:
      "对所有已匹配交易，统计实盘开仓时间相对回测开仓时间的平均绝对偏移秒数。数值越大，说明入场时机偏差越大。",
    平均出场延迟:
      "对所有已匹配交易，统计实盘平仓时间相对回测平仓时间的平均绝对偏移秒数。数值越大，说明出场时机偏差越大。",
    平均入场滑点:
      "已匹配交易中，实盘入场价格相对回测入场价格的不利偏移均值。正值代表实盘更差，负值代表实盘更优。",
    平均出场滑点:
      "已匹配交易中，实盘出场价格相对回测出场价格的不利偏移均值。正值代表实盘更差，负值代表实盘更优。",
    已匹配交易:
      "已经被判定为同一笔交易的配对数量。后续根因聚类、异常交易和逐笔明细都基于这些样本。",
  };

  function setReportLayoutStatus(text, type = "secondary") {
    const el = document.getElementById("report-layout-status");
    if (!el) return;
    el.textContent = text;
    el.className = `small text-${type}`;
  }

  function getReportGridHost() {
    return document.getElementById("report-grid");
  }

  function setCompareLayoutStatus(text, type = "secondary") {
    const el = document.getElementById("compare-layout-status");
    if (!el) return;
    el.textContent = text;
    el.className = `small text-${type}`;
  }

  function getCompareGridHost() {
    return document.getElementById("compare-grid");
  }

  function getCompareGridItem(id) {
    const host = getCompareGridHost();
    if (!host) return null;
    return host.querySelector(`.grid-stack-item[gs-id="${id}"]`);
  }

  function queueReportGridRefresh() {
    if (_reportGridRefreshTimer) clearTimeout(_reportGridRefreshTimer);
    _reportGridRefreshTimer = setTimeout(() => {
      if (_equityChart) _equityChart.resize();
    }, 100);
  }

  function queueCompareGridRefresh() {
    if (_compareGridRefreshTimer) clearTimeout(_compareGridRefreshTimer);
    _compareGridRefreshTimer = setTimeout(() => {
      if (_compareGrid) _compareGrid.compact();
    }, 100);
  }

  function recommendCompareWidgetHeight(rowCount, baseHeight, maxHeight) {
    if (!rowCount) return baseHeight;
    return Math.max(
      baseHeight,
      Math.min(maxHeight, baseHeight + Math.ceil(rowCount / 5)),
    );
  }

  function growCompareWidgetHeight(id, recommendedHeight) {
    const item = getCompareGridItem(id);
    if (!_compareGrid || !item) return;
    const currentHeight = Number(item.getAttribute("gs-h") || 1);
    if (recommendedHeight <= currentHeight) return;
    _compareGrid.update(item, { h: recommendedHeight });
  }

  function syncCompareWidgetHeights(body) {
    if (!_compareGrid) return;
    if (!body?.ready) {
      queueCompareGridRefresh();
      return;
    }

    const matchedCount = Math.min(30, body.matching?.matched?.length || 0);
    const anomalyCount = Math.min(
      20,
      body.matching?.top_anomalies?.length || 0,
    );
    const btOnlyCount = Math.min(50, body.matching?.bt_only?.length || 0);
    const liveOnlyCount = Math.min(50, body.matching?.live_only?.length || 0);
    const metricCount = body.overview?.metrics?.length || 0;
    const contribCount = body.attribution?.contributions?.length || 0;
    const clusterCount = body.attribution?.clusters?.length || 0;
    const breakdownCount = Math.min(12, body.matching?.matched?.length || 0);

    growCompareWidgetHeight(
      "compare-overview",
      body.overview?.cards?.length > 4 ? 4 : 3,
    );
    growCompareWidgetHeight(
      "compare-breakdown",
      recommendCompareWidgetHeight(breakdownCount, 4, 7),
    );
    growCompareWidgetHeight(
      "compare-contrib",
      recommendCompareWidgetHeight(contribCount, 4, 7),
    );
    growCompareWidgetHeight(
      "compare-clusters",
      recommendCompareWidgetHeight(clusterCount, 4, 7),
    );
    growCompareWidgetHeight(
      "compare-metrics",
      recommendCompareWidgetHeight(metricCount, 4, 6),
    );
    growCompareWidgetHeight(
      "compare-matched",
      recommendCompareWidgetHeight(matchedCount, 5, 11),
    );
    growCompareWidgetHeight(
      "compare-anomalies",
      recommendCompareWidgetHeight(anomalyCount, 5, 10),
    );
    growCompareWidgetHeight(
      "compare-bt-only",
      recommendCompareWidgetHeight(btOnlyCount, 4, 8),
    );
    growCompareWidgetHeight(
      "compare-live-only",
      recommendCompareWidgetHeight(liveOnlyCount, 4, 8),
    );
    queueCompareGridRefresh();
  }

  function collectReportLayout() {
    const host = getReportGridHost();
    if (!host) return [];
    return Array.from(host.querySelectorAll(".grid-stack-item")).map(
      (item) => ({
        id: item.getAttribute("gs-id"),
        x: Number(item.getAttribute("gs-x") || 0),
        y: Number(item.getAttribute("gs-y") || 0),
        w: Number(item.getAttribute("gs-w") || 12),
        h: Number(item.getAttribute("gs-h") || 1),
      }),
    );
  }

  function persistReportLayout() {
    try {
      localStorage.setItem(
        REPORT_LAYOUT_KEY,
        JSON.stringify(collectReportLayout()),
      );
      setReportLayoutStatus("布局已自动保存", "success");
    } catch (error) {
      console.error("Persist report layout error", error);
      setReportLayoutStatus("布局保存失败", "danger");
    }
  }

  function collectCompareLayout() {
    const host = getCompareGridHost();
    if (!host) return [];
    return Array.from(host.querySelectorAll(".grid-stack-item")).map(
      (item) => ({
        id: item.getAttribute("gs-id"),
        x: Number(item.getAttribute("gs-x") || 0),
        y: Number(item.getAttribute("gs-y") || 0),
        w: Number(item.getAttribute("gs-w") || 12),
        h: Number(item.getAttribute("gs-h") || 1),
      }),
    );
  }

  function persistCompareLayout() {
    try {
      localStorage.setItem(
        COMPARE_LAYOUT_KEY,
        JSON.stringify(collectCompareLayout()),
      );
      setCompareLayoutStatus("布局已自动保存", "success");
    } catch (error) {
      console.error("Persist compare layout error", error);
      setCompareLayoutStatus("布局保存失败", "danger");
    }
  }

  function applyReportLayout(layout) {
    const host = getReportGridHost();
    if (!_reportGrid || !host || !Array.isArray(layout)) return;
    layout.forEach((widget) => {
      const item = host.querySelector(`.grid-stack-item[gs-id="${widget.id}"]`);
      if (!item) return;
      _reportGrid.update(item, {
        x: Number(widget.x || 0),
        y: Number(widget.y || 0),
        w: Number(widget.w || 1),
        h: Number(widget.h || 1),
      });
    });
    queueReportGridRefresh();
  }

  function applyCompareLayout(layout) {
    const host = getCompareGridHost();
    if (!_compareGrid || !host || !Array.isArray(layout)) return;
    layout.forEach((widget) => {
      const item = host.querySelector(`.grid-stack-item[gs-id="${widget.id}"]`);
      if (!item) return;
      _compareGrid.update(item, {
        x: Number(widget.x || 0),
        y: Number(widget.y || 0),
        w: Number(widget.w || 1),
        h: Number(widget.h || 1),
      });
    });
    queueCompareGridRefresh();
  }

  function loadSavedReportLayout() {
    try {
      const raw = localStorage.getItem(REPORT_LAYOUT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      console.error("Parse report layout error", error);
      return null;
    }
  }

  function loadSavedCompareLayout() {
    try {
      const raw = localStorage.getItem(COMPARE_LAYOUT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      console.error("Parse compare layout error", error);
      return null;
    }
  }

  function initReportGrid() {
    const host = getReportGridHost();
    if (!host || typeof GridStack === "undefined") return;
    if (_reportGrid) {
      queueReportGridRefresh();
      return;
    }

    _reportGrid = GridStack.init(
      {
        column: 12,
        float: true,
        margin: 12,
        cellHeight: 72,
        handle: ".card-header, .report-widget-handle",
        resizable: { handles: "all" },
      },
      host,
    );

    applyReportLayout(loadSavedReportLayout() || REPORT_DEFAULT_LAYOUT);

    _reportGrid.on("change", () => {
      persistReportLayout();
      queueReportGridRefresh();
    });
    _reportGrid.on("dragstop", queueReportGridRefresh);
    _reportGrid.on("resizestop", queueReportGridRefresh);
  }

  function initCompareGrid() {
    const host = getCompareGridHost();
    if (!host || typeof GridStack === "undefined") return;
    if (_compareGrid) {
      queueCompareGridRefresh();
      return;
    }

    _compareGrid = GridStack.init(
      {
        column: 12,
        float: true,
        margin: 12,
        cellHeight: 72,
        handle: ".card-header, .report-widget-handle",
        resizable: { handles: "all" },
      },
      host,
    );

    applyCompareLayout(loadSavedCompareLayout() || COMPARE_DEFAULT_LAYOUT);

    _compareGrid.on("change", () => {
      persistCompareLayout();
      queueCompareGridRefresh();
    });
    _compareGrid.on("dragstop", queueCompareGridRefresh);
    _compareGrid.on("resizestop", queueCompareGridRefresh);
  }

  function syncReportLogTargets() {
    // Log is now only in the grid widget — nothing to sync
  }

  function toggleReportLog() {
    const body = document.getElementById("report-log-body");
    const icon = document.getElementById("report-log-toggle-icon");
    if (!body || !icon) return;
    const collapsed = body.style.display === "none";
    body.style.display = collapsed ? "" : "none";
    icon.className = collapsed
      ? "bi bi-chevron-up"
      : "bi bi-chevron-down";
  }

  function pos(v) {
    return v >= 0 ? "profit-up" : "profit-down";
  }

  function fmtSigned(value, digits = 2, suffix = "") {
    const number = Number(value || 0);
    return `${number >= 0 ? "+" : ""}${fmtN(number, digits)}${suffix}`;
  }

  function setNodeHtml(id, value, className = "value") {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = value;
    el.className = className;
  }

  function setNodeText(id, value, className = null) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    if (className) el.className = className;
  }

  function renderSummaryRows(tbodyId, rows) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    tbody.innerHTML = rows
      .map(([label, value, valueClass]) => {
        if (!label && !value) {
          return '<tr class="report-summary-divider"><td colspan="2"></td></tr>';
        }
        return `<tr>
          <td class="text-muted">${label}</td>
          <td class="fw-bold ${valueClass || ""}">${value}</td>
        </tr>`;
      })
      .join("");
  }

  function setCompareStatus(text, type = "secondary") {
    const el = document.getElementById("compare-status");
    if (el) {
      el.textContent = text;
      el.className = `small text-${type}`;
    }

    const badgeEl = document.getElementById("compare-state-badge");
    if (!badgeEl) return;
    const typeMap = {
      success: "compare-pill-success",
      warning: "compare-pill-warning",
      danger: "compare-pill-danger",
      info: "compare-pill-info",
      secondary: "compare-pill-muted",
    };
    badgeEl.textContent = text;
    badgeEl.className = `compare-pill ${typeMap[type] || "compare-pill-muted"}`;
  }

  function setCompareMeta(text) {
    const el = document.getElementById("compare-meta");
    if (el) el.textContent = text;
  }

  function setCompareNoteStatus(text) {
    const el = document.getElementById("compare-inline-status");
    if (!el) return;
    el.textContent = text;
  }

  function setCompareNoteMeta(text) {
    const el = document.getElementById("compare-inline-meta");
    if (!el) return;
    el.textContent = text;
  }

  function buildCompareScopeText(body) {
    const liveCount = body?.overview?.live_trade_count || 0;
    const btCount = body?.overview?.bt_trade_count || 0;
    const matchedCount =
      body?.overview?.matched_count || body?.matching?.matched?.length || 0;
    return `实盘 ${liveCount} 笔 / 回测 ${btCount} 笔 / 已匹配 ${matchedCount} 笔`;
  }

  function setCompareDiagnosis(text) {
    const el = document.getElementById("compare-diagnosis");
    if (!el) return;
    el.textContent = text;
  }

  function setCompareScore(score) {
    const el = document.getElementById("compare-score");
    if (!el) return;
    el.textContent = score == null ? "-" : String(score);
  }

  function setCompareMetricCount(count) {
    const el = document.getElementById("compare-metric-count");
    if (!el) return;
    el.textContent = String(count || 0);
  }

  function setCompareMatchCount(count) {
    const el = document.getElementById("compare-match-count");
    if (!el) return;
    el.textContent = String(count || 0);
  }

  function setCompareFileName(name) {
    const el = document.getElementById("compare-file");
    if (!el) return;
    el.textContent = name || "未上传";
  }

  function getCompareHelpText(label) {
    return COMPARE_FIELD_HELP[label] || "";
  }

  function getCompareHelpMarkup(label) {
    const helpText = getCompareHelpText(label);
    if (!helpText) return "";
    return `<span class="compare-help" tabindex="0"><span class="compare-help-trigger">?</span><span class="compare-help-pop">${helpText}</span></span>`;
  }

  function renderCompareTableControls(hostId, stateKey, totalRows) {
    const host = document.getElementById(hostId);
    if (!host) return;
    const currentLimit = COMPARE_STATE.limits[stateKey] || 20;
    const options = [20, 50, 100];
    host.innerHTML = `
      <span class="compare-table-count">显示 ${Math.min(totalRows || 0, currentLimit)} / ${totalRows || 0}</span>
      <div class="btn-group btn-group-sm compare-limit-switch" role="group">
        ${options
          .map(
            (limit) =>
              `<button class="btn ${currentLimit === limit ? "btn-info" : "btn-outline-secondary"}" onclick="setCompareTableLimit('${stateKey}', ${limit})">${limit}</button>`,
          )
          .join("")}
      </div>
    `;
  }

  function renderCompareRows(metrics) {
    const tbody = document.getElementById("compare-body");
    if (!tbody) return;
    setCompareMetricCount(metrics?.length || 0);
    if (!metrics?.length) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="text-center py-3 text-muted">上传回测结果后显示对比</td></tr>';
      return;
    }

    tbody.innerHTML = metrics
      .map((metric) => {
        const diff = Number(metric.diff_pct || 0);
        const cls = diff >= 0 ? "profit-up" : "profit-down";
        const unit = metric.unit || "";
        return `<tr>
        <td class="text-muted">${metric.label}</td>
        <td>${fmtN(metric.live, 2)}${unit}</td>
        <td>${fmtN(metric.bt, 2)}${unit}</td>
        <td class="${cls}">${diff >= 0 ? "+" : ""}${fmtN(diff, 1)}%</td>
      </tr>`;
      })
      .join("");
  }

  function renderCompareOverviewCards(cards) {
    const host = document.getElementById("compare-overview-cards");
    if (!host) return;
    if (!cards?.length) {
      host.innerHTML = "";
      return;
    }
    host.innerHTML = cards
      .map(
        (card) => `
        <div class="col-sm-6 col-xl-3">
          <div class="card bg-secondary border-0 shadow-sm compare-overview-card h-100">
            <div class="card-body">
              <div class="compare-overview-label-row">
                <div class="compare-overview-label">${card.label}</div>
                ${getCompareHelpMarkup(card.label)}
              </div>
              <div class="compare-overview-value">${fmtN(card.value, typeof card.value === "number" && !Number.isInteger(card.value) ? 1 : 0)}<span class="compare-overview-unit">${card.unit || ""}</span></div>
            </div>
          </div>
        </div>`,
      )
      .join("");
  }

  function renderCompareContributionRows(rows) {
    const tbody = document.getElementById("compare-contrib-body");
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="3" class="text-center py-3 text-muted">暂无可用归因</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(
        (row) => `<tr>
          <td>${row.label}</td>
          <td class="text-end">${fmtN(row.value, 2)}</td>
          <td class="text-end">${fmtN(row.share_pct, 1)}%</td>
        </tr>`,
      )
      .join("");
  }

  function renderCompareClusterRows(rows) {
    const tbody = document.getElementById("compare-cluster-body");
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="5" class="text-center py-3 text-muted">暂无聚类结果</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .map(
        (row) => `<tr>
          <td>${row.label}</td>
          <td class="text-end">${row.count}</td>
          <td class="text-end">${fmtN(row.avg_entry_delay_sec, 1)} s</td>
          <td class="text-end">${fmtN(row.avg_exit_delay_sec, 1)} s</td>
          <td class="text-end ${pos(row.avg_pnl_diff_pct || 0)}">${row.avg_pnl_diff_pct >= 0 ? "+" : ""}${fmtN(row.avg_pnl_diff_pct, 2)}%</td>
        </tr>`,
      )
      .join("");
  }

  function renderCompareAnomalyRows(rows) {
    const tbody = document.getElementById("compare-anomaly-body");
    if (!tbody) return;
    const totalRows = rows?.length || 0;
    renderCompareTableControls(
      "compare-anomaly-controls",
      "anomalies",
      totalRows,
    );
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="10" class="text-center py-3 text-muted">暂无异常交易</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .slice(0, COMPARE_STATE.limits.anomalies || 20)
      .map(
        (row) => `<tr>
          <td>${row.pair}</td>
          <td>${row.side === "short" ? "空" : "多"}</td>
          <td>${row.enter_tag || "-"}</td>
          <td class="text-end">${fmtN(row.entry_delay_sec, 1)} s</td>
          <td class="text-end ${pos(-row.entry_slippage_pct || 0)}">${row.entry_slippage_pct >= 0 ? "+" : ""}${fmtN(row.entry_slippage_pct, 3)}%</td>
          <td class="text-end ${pos(-row.exit_slippage_pct || 0)}">${row.exit_slippage_pct >= 0 ? "+" : ""}${fmtN(row.exit_slippage_pct, 3)}%</td>
          <td>${row.bt_exit_reason}</td>
          <td>${row.live_exit_reason}</td>
          <td class="text-end ${pos(row.pnl_diff_pct || 0)}">${row.pnl_diff_pct >= 0 ? "+" : ""}${fmtN(row.pnl_diff_pct, 2)}%</td>
          <td class="text-end">${fmtN(row.match_confidence, 1)}%</td>
        </tr>`,
      )
      .join("");
  }

  function renderCompareUnmatchedRows(tbodyId, rows) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    const controlIdMap = {
      "compare-bt-only-body": ["compare-bt-only-controls", "btOnly"],
      "compare-live-only-body": ["compare-live-only-controls", "liveOnly"],
    };
    const [hostId, stateKey] = controlIdMap[tbodyId] || [];
    if (hostId && stateKey) {
      renderCompareTableControls(hostId, stateKey, rows?.length || 0);
    }
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center py-3 text-muted">暂无未匹配交易</td></tr>';
      return;
    }
    tbody.innerHTML = rows
      .slice(0, COMPARE_STATE.limits[stateKey] || 20)
      .map(
        (row) => `<tr>
          <td>${row.pair}</td>
          <td>${row.side === "short" ? "空" : "多"}</td>
          <td>${row.enter_tag || "-"}</td>
          <td>${row.entry_time}</td>
          <td>${row.exit_reason}</td>
          <td class="text-end ${pos(row.profit_pct || 0)}">${row.profit_pct >= 0 ? "+" : ""}${fmtN(row.profit_pct, 2)}%</td>
        </tr>`,
      )
      .join("");
  }

  function setSelectOptions(id, options, placeholder) {
    const el = document.getElementById(id);
    if (!el) return;
    const currentValue = el.value;
    el.innerHTML = [
      `<option value="">${placeholder}</option>`,
      ...options.map((value) => `<option value="${value}">${value}</option>`),
    ].join("");
    if (options.includes(currentValue)) {
      el.value = currentValue;
    }
  }

  function populateCompareFilterOptions(matchedRows) {
    const rows = matchedRows || [];
    const uniq = (list) =>
      Array.from(
        new Set(list.filter((value) => value && value !== "-")),
      ).sort();
    setSelectOptions(
      "compare-filter-pair",
      uniq(rows.map((row) => row.pair)),
      "全部交易对",
    );
    setSelectOptions(
      "compare-filter-tag",
      uniq(rows.map((row) => row.enter_tag)),
      "全部标签",
    );
    setSelectOptions(
      "compare-filter-bucket",
      uniq(rows.map((row) => row.bucket)),
      "全部问题类型",
    );
    setSelectOptions(
      "compare-filter-exit-reason",
      uniq(rows.map((row) => row.live_exit_reason)),
      "全部退出原因",
    );

    const sideEl = document.getElementById("compare-filter-side");
    if (sideEl) sideEl.value = COMPARE_STATE.filters.side || "";
  }

  function getCompareMatchedRows() {
    return COMPARE_STATE.raw?.matching?.matched || [];
  }

  function getFilteredCompareRows() {
    const rows = getCompareMatchedRows();
    const filters = COMPARE_STATE.filters;
    return rows.filter((row) => {
      if (filters.pair && row.pair !== filters.pair) return false;
      if (filters.enterTag && row.enter_tag !== filters.enterTag) return false;
      if (filters.side && row.side !== filters.side) return false;
      if (filters.bucket && row.bucket !== filters.bucket) return false;
      if (filters.exitReason && row.live_exit_reason !== filters.exitReason)
        return false;
      return true;
    });
  }

  function renderCompareFilterSummary(rows) {
    const countEl = document.getElementById("compare-filter-count");
    const pnlEl = document.getElementById("compare-filter-pnl");
    const entryDelayEl = document.getElementById("compare-filter-entry-delay");
    const exitMismatchEl = document.getElementById(
      "compare-filter-exit-mismatch",
    );
    if (!countEl || !pnlEl || !entryDelayEl || !exitMismatchEl) return;

    const count = rows.length;
    countEl.textContent = `${count} 笔`;
    if (!count) {
      pnlEl.textContent = "-";
      pnlEl.className = "compare-filter-stat-value";
      entryDelayEl.textContent = "-";
      exitMismatchEl.textContent = "-";
      return;
    }

    const avgPnl =
      rows.reduce((sum, row) => sum + Number(row.pnl_diff_pct || 0), 0) / count;
    const avgEntryDelay =
      rows.reduce(
        (sum, row) => sum + Math.abs(Number(row.entry_delay_sec || 0)),
        0,
      ) / count;
    const exitMismatchCount = rows.filter(
      (row) => row.bt_exit_reason !== row.live_exit_reason,
    ).length;

    pnlEl.textContent = `${avgPnl >= 0 ? "+" : ""}${fmtN(avgPnl, 2)}%`;
    pnlEl.className = `compare-filter-stat-value ${pos(avgPnl)}`;
    entryDelayEl.textContent = `${fmtN(avgEntryDelay, 1)} s`;
    exitMismatchEl.textContent = `${exitMismatchCount} / ${count}`;
  }

  function renderCompareBreakdownRows(rows, groupBy) {
    const tbody = document.getElementById("compare-breakdown-body");
    if (!tbody) return;
    if (!rows?.length) {
      renderCompareTableControls("compare-breakdown-controls", "breakdown", 0);
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center py-3 text-muted">当前筛选下没有匹配交易</td></tr>';
      return;
    }

    const grouped = new Map();
    rows.forEach((row) => {
      const key = row[groupBy] || "-";
      const item = grouped.get(key) || {
        key,
        count: 0,
        entryDelay: 0,
        exitDelay: 0,
        pnlDiff: 0,
        confidence: 0,
      };
      item.count += 1;
      item.entryDelay += Math.abs(Number(row.entry_delay_sec || 0));
      item.exitDelay += Math.abs(Number(row.exit_delay_sec || 0));
      item.pnlDiff += Number(row.pnl_diff_pct || 0);
      item.confidence += Number(row.match_confidence || 0);
      grouped.set(key, item);
    });

    const items = Array.from(grouped.values())
      .map((item) => ({
        ...item,
        avgEntryDelay: item.entryDelay / item.count,
        avgExitDelay: item.exitDelay / item.count,
        avgPnlDiff: item.pnlDiff / item.count,
        avgConfidence: item.confidence / item.count,
      }))
      .sort(
        (left, right) => Math.abs(right.avgPnlDiff) - Math.abs(left.avgPnlDiff),
      );

    renderCompareTableControls(
      "compare-breakdown-controls",
      "breakdown",
      items.length,
    );

    tbody.innerHTML = items
      .slice(0, COMPARE_STATE.limits.breakdown || 20)
      .map(
        (item) => `<tr>
          <td>${item.key}</td>
          <td class="text-end">${item.count}</td>
          <td class="text-end">${fmtN(item.avgEntryDelay, 1)} s</td>
          <td class="text-end">${fmtN(item.avgExitDelay, 1)} s</td>
          <td class="text-end ${pos(item.avgPnlDiff)}">${item.avgPnlDiff >= 0 ? "+" : ""}${fmtN(item.avgPnlDiff, 2)}%</td>
          <td class="text-end">${fmtN(item.avgConfidence, 1)}%</td>
        </tr>`,
      )
      .join("");
  }

  function renderCompareMatchedRows(rows) {
    const tbody = document.getElementById("compare-matched-body");
    if (!tbody) return;
    renderCompareTableControls(
      "compare-matched-controls",
      "matched",
      rows?.length || 0,
    );
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="11" class="text-center py-3 text-muted">当前筛选下没有匹配交易</td></tr>';
      return;
    }

    const items = [...rows]
      .sort(
        (left, right) =>
          Math.abs(right.pnl_diff_pct) - Math.abs(left.pnl_diff_pct),
      )
      .slice(0, COMPARE_STATE.limits.matched || 20);

    tbody.innerHTML = items
      .map(
        (row) => `<tr>
          <td>${row.pair}</td>
          <td>${row.side === "short" ? "空" : "多"}</td>
          <td>${row.enter_tag || "-"}</td>
          <td>${row.bucket || "-"}</td>
          <td class="text-end">${fmtN(row.entry_delay_sec, 1)} s</td>
          <td class="text-end">${fmtN(row.exit_delay_sec, 1)} s</td>
          <td class="text-end ${pos(-row.entry_slippage_pct || 0)}">${row.entry_slippage_pct >= 0 ? "+" : ""}${fmtN(row.entry_slippage_pct, 3)}%</td>
          <td class="text-end ${pos(-row.exit_slippage_pct || 0)}">${row.exit_slippage_pct >= 0 ? "+" : ""}${fmtN(row.exit_slippage_pct, 3)}%</td>
          <td class="text-end ${pos(-row.duration_diff_min || 0)}">${row.duration_diff_min >= 0 ? "+" : ""}${fmtN(row.duration_diff_min, 1)} min</td>
          <td class="text-end ${pos(row.pnl_diff_pct || 0)}">${row.pnl_diff_pct >= 0 ? "+" : ""}${fmtN(row.pnl_diff_pct, 2)}%</td>
          <td class="text-end">${fmtN(row.match_confidence, 1)}%</td>
        </tr>`,
      )
      .join("");
  }

  function updateCompareDrilldown() {
    const rows = getFilteredCompareRows();
    renderCompareFilterSummary(rows);
    renderCompareBreakdownRows(rows, COMPARE_STATE.groupBy);
    renderCompareMatchedRows(rows);
  }

  function resetCompareDrilldown() {
    COMPARE_STATE.raw = null;
    COMPARE_STATE.groupBy = "pair";
    COMPARE_STATE.limits = {
      breakdown: 20,
      matched: 20,
      anomalies: 20,
      btOnly: 20,
      liveOnly: 20,
    };
    COMPARE_STATE.filters = {
      pair: "",
      enterTag: "",
      side: "",
      bucket: "",
      exitReason: "",
    };
    populateCompareFilterOptions([]);
    const groupEl = document.getElementById("compare-group-by");
    if (groupEl) groupEl.value = "pair";
    renderCompareFilterSummary([]);
    renderCompareBreakdownRows([], COMPARE_STATE.groupBy);
    renderCompareMatchedRows([]);
  }

  async function loadBacktestMeta() {
    try {
      const data = await fetch("/api/backtest/data").then((r) => r.json());
      setCompareFileName(data?.filename || "未上传");
    } catch (e) {
      setCompareFileName("未上传");
    }
  }

  function getSectionRows(sectionKey, rows) {
    const state = REPORT_SECTION_STATE[sectionKey];
    REPORT_SECTION_DATA[sectionKey] = rows || [];
    if (state.expanded) return REPORT_SECTION_DATA[sectionKey];

    const totalPages = Math.max(
      1,
      Math.ceil(REPORT_SECTION_DATA[sectionKey].length / state.pageSize),
    );
    if (state.page > totalPages) state.page = totalPages;
    const start = (state.page - 1) * state.pageSize;
    return REPORT_SECTION_DATA[sectionKey].slice(start, start + state.pageSize);
  }

  function renderSectionControls(sectionKey) {
    const map = {
      pair: "report-pair-controls",
      open: "report-open-controls",
      enterTag: "report-enter-tag-controls",
      exitReason: "report-exit-reason-controls",
      mixTag: "report-mix-tag-controls",
    };
    const host = document.getElementById(map[sectionKey]);
    if (!host) return;

    const rows = REPORT_SECTION_DATA[sectionKey] || [];
    const state = REPORT_SECTION_STATE[sectionKey];
    const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    const pageInfo = rows.length
      ? state.expanded
        ? `全部 ${rows.length} 条`
        : `第 ${state.page}/${totalPages} 页`
      : "0 条";

    host.innerHTML = `
      <span class="report-page-info">${pageInfo}</span>
      <button class="btn btn-sm report-control-btn" ${state.expanded || state.page <= 1 ? "disabled" : ""} onclick="changeReportSectionPage('${sectionKey}', -1)">上一页</button>
      <button class="btn btn-sm report-control-btn" ${state.expanded || state.page >= totalPages ? "disabled" : ""} onclick="changeReportSectionPage('${sectionKey}', 1)">下一页</button>
      <button class="btn btn-sm report-control-btn report-control-btn-ghost" onclick="toggleReportSection('${sectionKey}')">${state.expanded ? "收起" : "显示全部"}</button>
    `;
  }

  function buildAlignedRows(rows, keyLabel = "key") {
    return rows
      .map((row) => {
        const winrate = row.winrate != null ? fmtN(row.winrate * 100, 1) : "-";
        const label = row[keyLabel] ?? row.key ?? "-";
        const rowClass = label === "TOTAL" ? "report-total-row" : "";
        return `<tr>
        <td class="text-muted fw-bold ${rowClass}">${label}</td>
        <td class="text-end">${row.trades ?? 0}</td>
        <td class="text-end ${pos(row.profit_mean_pct || 0)}">${fmtN(row.profit_mean_pct || 0, 2)}</td>
        <td class="text-end ${pos(row.profit_total_abs || 0)}">${(row.profit_total_abs || 0) >= 0 ? "+" : ""}${fmtN(row.profit_total_abs || 0, 3)}</td>
        <td class="text-end ${pos(row.profit_total_pct || 0)}">${(row.profit_total_pct || 0) >= 0 ? "+" : ""}${fmtN(row.profit_total_pct || 0, 2)}</td>
        <td class="text-end">${row.duration_avg || "-"}</td>
        <td class="text-end small">${row.wins ?? 0} ${row.draws ?? 0} ${row.losses ?? 0} <span class="ms-1">${winrate}%</span></td>
      </tr>`;
      })
      .join("");
  }

  function buildMixRows(rows) {
    return rows
      .map((row) => {
        const enterTag = row.enter_tag || row.key || "-";
        const exitReason = row.exit_reason || "-";
        const winrate = row.winrate != null ? fmtN(row.winrate * 100, 1) : "-";
        const rowClass = enterTag === "TOTAL" ? "report-total-row" : "";
        return `<tr>
        <td class="text-muted fw-bold ${rowClass}">${enterTag}</td>
        <td class="text-muted">${exitReason}</td>
        <td class="text-end">${row.trades ?? 0}</td>
        <td class="text-end ${pos(row.profit_mean_pct || 0)}">${fmtN(row.profit_mean_pct || 0, 2)}</td>
        <td class="text-end ${pos(row.profit_total_abs || 0)}">${(row.profit_total_abs || 0) >= 0 ? "+" : ""}${fmtN(row.profit_total_abs || 0, 3)}</td>
        <td class="text-end ${pos(row.profit_total_pct || 0)}">${(row.profit_total_pct || 0) >= 0 ? "+" : ""}${fmtN(row.profit_total_pct || 0, 2)}</td>
        <td class="text-end">${row.duration_avg || "-"}</td>
        <td class="text-end small">${row.wins ?? 0} ${row.draws ?? 0} ${row.losses ?? 0} <span class="ms-1">${winrate}%</span></td>
      </tr>`;
      })
      .join("");
  }

  function renderAlignedStatsTable(
    tbodyId,
    rows,
    keyLabel = "key",
    sectionKey = null,
  ) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="7" class="text-center py-4 text-muted">无数据</td></tr>';
      if (sectionKey) {
        REPORT_SECTION_DATA[sectionKey] = [];
        renderSectionControls(sectionKey);
      }
      return;
    }
    const renderRows = sectionKey ? getSectionRows(sectionKey, rows) : rows;
    tbody.innerHTML = buildAlignedRows(renderRows, keyLabel);
    if (sectionKey) renderSectionControls(sectionKey);
  }

  function renderMixTagStatsTable(tbodyId, rows, sectionKey = null) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="text-center py-4 text-muted">无数据</td></tr>';
      if (sectionKey) {
        REPORT_SECTION_DATA[sectionKey] = [];
        renderSectionControls(sectionKey);
      }
      return;
    }
    const renderRows = sectionKey ? getSectionRows(sectionKey, rows) : rows;
    tbody.innerHTML = buildMixRows(renderRows);
    if (sectionKey) renderSectionControls(sectionKey);
  }

  function resetReportSectionState() {
    Object.values(REPORT_SECTION_STATE).forEach((state) => {
      state.page = 1;
      state.expanded = false;
    });
  }

  function deriveInitialCapital(reportData, trades) {
    const directCandidates = [
      reportData?.starting_balance,
      reportData?.available_capital,
      reportData?.dry_run_wallet,
      reportData?.dry_run_wallet_start,
    ];
    for (const candidate of directCandidates) {
      const value = Number(candidate);
      if (Number.isFinite(value) && value > 0) return value;
    }

    const profitTotal = Number(reportData?.profit_total);
    const profitTotalAbs = Number(reportData?.profit_total_abs);
    if (
      Number.isFinite(profitTotal) &&
      Number.isFinite(profitTotalAbs) &&
      profitTotal !== 0
    ) {
      const inferred = profitTotalAbs / profitTotal;
      if (Number.isFinite(inferred) && inferred > 0) return inferred;
    }

    const firstStake = Number(
      (trades || []).find((trade) => Number(trade?.stake_amount) > 0)
        ?.stake_amount,
    );
    if (Number.isFinite(firstStake) && firstStake > 0) {
      return firstStake * 10;
    }

    return 1000;
  }

  function renderEquityChart(reportData) {
    const trades = reportData?.trades || [];
    const host = document.getElementById("report-equity-chart");
    const metaEl = document.getElementById("report-equity-meta");
    const currentEl = document.getElementById("report-equity-current");
    const peakEl = document.getElementById("report-equity-peak");
    const drawdownEl = document.getElementById("report-equity-drawdown");
    if (!host || !metaEl || !currentEl || !peakEl || !drawdownEl) return;

    if (typeof echarts === "undefined") {
      host.innerHTML =
        '<div class="text-secondary small">ECharts 未加载，暂时无法显示交互图表</div>';
      metaEl.textContent = "图表库加载失败";
      return;
    }

    const closedTrades = [...(trades || [])]
      .filter((trade) => trade && !trade.is_open)
      .sort((left, right) => {
        const lt =
          Date.parse(left.close_date || left.close_timestamp || 0) || 0;
        const rt =
          Date.parse(right.close_date || right.close_timestamp || 0) || 0;
        return lt - rt;
      });

    if (!closedTrades.length) {
      metaEl.textContent = "暂无可绘制的已平仓资金数据";
      currentEl.textContent = "-";
      peakEl.textContent = "-";
      drawdownEl.textContent = "-";
      host.innerHTML =
        '<div class="text-secondary small">暂无可绘制的已平仓资金数据</div>';
      if (_equityChart) {
        _equityChart.dispose();
        _equityChart = null;
      }
      return;
    }

    const initialCapital = deriveInitialCapital(reportData, closedTrades);
    let cumulativeProfit = 0;
    let runningPeak = Number.NEGATIVE_INFINITY;
    let peakIndex = 0;
    let currentPeak = Number.NEGATIVE_INFINITY;
    const points = closedTrades.map((trade, index) => {
      cumulativeProfit += Number(trade.profit_abs || 0);
      const totalEquity = initialCapital + cumulativeProfit;
      if (totalEquity >= runningPeak) {
        runningPeak = totalEquity;
        peakIndex = index;
      }
      currentPeak = Math.max(currentPeak, totalEquity);
      return {
        label: (trade.close_date || trade.open_date || "")
          .slice(5, 16)
          .replace("T", " "),
        fullLabel: trade.close_date || trade.open_date || "-",
        equity: totalEquity,
        profit: cumulativeProfit,
        peak: currentPeak,
        drawdownAbs: totalEquity - currentPeak,
        drawdownPct:
          currentPeak !== 0
            ? ((totalEquity - currentPeak) / Math.abs(currentPeak)) * 100
            : 0,
      };
    });

    const currentEquity = points[points.length - 1].equity;
    const peakEquity = Math.max(...points.map((point) => point.peak));
    const drawdownAbs = currentEquity - peakEquity;
    const drawdownPct =
      peakEquity !== 0 ? (drawdownAbs / Math.abs(peakEquity)) * 100 : 0;
    const drawdownGap = points.map((point) =>
      Math.max(0, point.peak - point.equity),
    );

    currentEl.textContent = `${fmtN(currentEquity, 2)} U`;
    peakEl.textContent = `${fmtN(peakEquity, 2)} U`;
    drawdownEl.textContent = `${drawdownAbs >= 0 ? "+" : ""}${fmtN(drawdownAbs, 2)} U / ${drawdownPct >= 0 ? "+" : ""}${fmtN(drawdownPct, 2)}%`;
    drawdownEl.className = `report-equity-value ${drawdownAbs < 0 ? "profit-down" : "profit-up"}`;
    metaEl.textContent = `初始资金 ${fmtN(initialCapital, 2)} U，基于 ${closedTrades.length} 笔已平仓交易按平仓时间计算权益`;

    if (!_equityChart) {
      host.innerHTML = "";
      // 如果容器尺寸为 0（grid-stack 未完成布局），延迟初始化
      if (host.offsetWidth === 0 || host.offsetHeight === 0) {
        setTimeout(() => {
          if (host.offsetWidth > 0 && host.offsetHeight > 0) {
            host.innerHTML = "";
            _equityChart = echarts.init(host, null, { renderer: "canvas" });
            _bindEquityResize();
            const catData = points.map((p) => p.label);
            const pkData = points.map((p) => p.peak);
            const eqData = points.map((p) => p.equity);
            const mkData = drawdownAbs < 0 && peakIndex < points.length - 1
              ? [[{ xAxis: catData[peakIndex] }, { xAxis: catData[catData.length - 1] }]] : [];
            _applyChartOptions(points, catData, pkData, eqData, drawdownGap, peakIndex, drawdownAbs, currentEquity, peakEquity, mkData);
          }
        }, 300);
        return;
      }
      _equityChart = echarts.init(host, null, { renderer: "canvas" });
    }

    _bindEquityResize();

    const categoryData = points.map((point) => point.label);
    const peakData = points.map((point) => point.peak);
    const equityData = points.map((point) => point.equity);
    const markAreaData =
      drawdownAbs < 0 && peakIndex < points.length - 1
        ? [
            [
              { xAxis: categoryData[peakIndex] },
              { xAxis: categoryData[categoryData.length - 1] },
            ],
          ]
        : [];

    _applyChartOptions(points, categoryData, peakData, equityData, drawdownGap, peakIndex, drawdownAbs, currentEquity, peakEquity, markAreaData);
  }

  function _bindEquityResize() {
    if (!_equityResizeBound) {
      window.addEventListener("resize", () => {
        if (_equityChart) _equityChart.resize();
      });
      _equityResizeBound = true;
    }
  }

  function _applyChartOptions(points, categoryData, peakData, equityData, drawdownGap, peakIndex, drawdownAbs, currentEquity, peakEquity, markAreaData) {
    if (!_equityChart) return;
    _equityChart.setOption(
      {
        animation: false,
        grid: { left: 56, right: 22, top: 18, bottom: 56 },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(11, 24, 30, 0.96)",
          borderColor: "rgba(113, 181, 193, 0.24)",
          textStyle: { color: "#f3f4f6" },
          axisPointer: {
            type: "line",
            lineStyle: { color: "rgba(159, 176, 183, 0.35)", width: 1 },
          },
          formatter(params) {
            const idx = params?.[0]?.dataIndex ?? 0;
            const point = points[idx];
            return [
              `<div style="font-weight:700;margin-bottom:6px;">${point.fullLabel.replace("T", " ")}</div>`,
              `<div>总资金: <span style="color:#29c7d8;font-weight:700;">${fmtN(point.equity, 2)} U</span></div>`,
              `<div>累计收益: <span style="color:#8fdbe4;font-weight:700;">${point.profit >= 0 ? "+" : ""}${fmtN(point.profit, 2)} U</span></div>`,
              `<div>历史权益峰值: <span style="color:#f2f4f7;font-weight:700;">${fmtN(point.peak, 2)} U</span></div>`,
              `<div>当时资金回撤: <span style="color:${point.drawdownAbs < 0 ? "#ef5350" : "#12bb7b"};font-weight:700;">${point.drawdownAbs >= 0 ? "+" : ""}${fmtN(point.drawdownAbs, 2)} U / ${point.drawdownPct >= 0 ? "+" : ""}${fmtN(point.drawdownPct, 2)}%</span></div>`,
            ].join("");
          },
        },
        xAxis: {
          type: "category",
          data: categoryData,
          boundaryGap: false,
          axisLine: { lineStyle: { color: "rgba(113, 181, 193, 0.20)" } },
          axisLabel: { color: "#93a7af" },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: "rgba(159, 176, 183, 0.14)" } },
          axisLabel: {
            color: "#93a7af",
            formatter(value) {
              return `${fmtN(value, 0)}U`;
            },
          },
        },
        dataZoom: [
          {
            type: "inside",
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
          },
          {
            type: "slider",
            height: 18,
            bottom: 18,
            borderColor: "rgba(113, 181, 193, 0.12)",
            backgroundColor: "rgba(18, 29, 34, 0.9)",
            fillerColor: "rgba(41, 199, 216, 0.18)",
            dataBackground: {
              lineStyle: { color: "rgba(159, 176, 183, 0.28)" },
              areaStyle: { color: "rgba(159, 176, 183, 0.10)" },
            },
            textStyle: { color: "#93a7af" },
          },
        ],
        series: [
          {
            name: "总资金",
            type: "line",
            data: equityData,
            showSymbol: false,
            smooth: 0.2,
            lineStyle: { width: 3, color: "#29c7d8" },
            emphasis: { focus: "series" },
            markArea: markAreaData.length
              ? {
                  silent: true,
                  itemStyle: { color: "rgba(239, 83, 80, 0.08)" },
                  data: markAreaData,
                }
              : undefined,
            markPoint: {
              symbolSize: 46,
              label: { color: "#f3f4f6", fontSize: 10 },
              itemStyle: {
                color: "#29c7d8",
                borderColor: "#081419",
                borderWidth: 2,
              },
              data: [
                {
                  name: "峰值",
                  coord: [categoryData[peakIndex], peakEquity],
                  value: "峰值",
                },
                {
                  name: "当前",
                  coord: [categoryData[categoryData.length - 1], currentEquity],
                  value: "当前",
                },
              ],
            },
          },
          {
            name: "历史权益峰值",
            type: "line",
            data: peakData,
            showSymbol: false,
            smooth: 0,
            lineStyle: {
              width: 1.5,
              color: "rgba(255,255,255,0.45)",
              type: "dashed",
            },
            tooltip: { show: false },
          },
          {
            name: "回撤基线",
            type: "line",
            data: equityData,
            stack: "drawdown-band",
            showSymbol: false,
            lineStyle: { opacity: 0 },
            areaStyle: { opacity: 0 },
            tooltip: { show: false },
          },
          {
            name: "回撤阴影",
            type: "line",
            data: drawdownGap,
            stack: "drawdown-band",
            showSymbol: false,
            lineStyle: { opacity: 0 },
            areaStyle: { color: "rgba(239, 83, 80, 0.20)" },
            tooltip: { show: false },
          },
        ],
      },
      true,
    );

    _equityChart.resize();
  }

  function renderTopKpis(d) {
    setNodeHtml("report-kpi-trades", fmtN(d.total_trades || 0, 0));
    setNodeHtml(
      "report-kpi-pnl",
      `${fmtSigned(d.profit_total_abs, 2, " U")}`,
      `value ${pos(d.profit_total_abs || 0)}`,
    );
    setNodeHtml(
      "report-kpi-return",
      `${fmtSigned((d.profit_total || 0) * 100, 2, "%")}`,
      `value ${pos(d.profit_total || 0)}`,
    );
    setNodeHtml("report-kpi-winrate", `${fmtN((d.winrate || 0) * 100, 1)}%`);
    setNodeHtml("report-kpi-sharpe", fmtN(d.sharpe || 0, 2));
    setNodeHtml("report-kpi-pf", fmtN(d.profit_factor || 0, 2));
  }

  function renderSummaryBlocks(d) {
    renderSummaryRows("report-summary-core-body", [
      ["实盘起止", `${d.backtest_start || "-"} -> ${d.backtest_end || "-"}`],
      [
        "总计 / 日均交易次数",
        `${fmtN(d.total_trades || 0, 0)} / ${fmtN(d.trades_per_day || 0, 2)}`,
      ],
      [
        "初始 / 最终余额",
        `${fmtN(d.starting_balance || 0, 2)} U / ${fmtN(d.final_balance || 0, 2)} U`,
      ],
      [
        "净利润",
        `${fmtSigned(d.profit_total_abs, 3, " U")}`,
        pos(d.profit_total_abs || 0),
      ],
      [
        "总收益率",
        `${fmtSigned((d.profit_total || 0) * 100, 2, "%")}`,
        pos(d.profit_total || 0),
      ],
      ["平均单笔头寸", `${fmtN(d.avg_stake_amount || 0, 3)} U`],
      ["总交易成交额", `${fmtN(d.total_volume || 0, 3)} U`],
      ["", ""],
      [
        "盈利 / 持平 / 亏损天数",
        `${d.winning_days || 0} / ${d.draw_days || 0} / ${d.losing_days || 0}`,
      ],
      [
        "获利最高日",
        `${fmtSigned(d.backtest_best_day_abs, 3, " U")}`,
        pos(d.backtest_best_day_abs || 0),
      ],
      [
        "亏损最高日",
        `${fmtSigned(d.backtest_worst_day_abs, 3, " U")}`,
        pos(d.backtest_worst_day_abs || 0),
      ],
      [
        "最大连续盈利 / 亏损次数",
        `${d.max_consecutive_wins || 0} / ${d.max_consecutive_losses || 0}`,
      ],
    ]);

    renderSummaryRows("report-summary-risk-body", [
      ["索提诺比率", fmtN(d.sortino || 0, 2)],
      ["夏普比率", fmtN(d.sharpe || 0, 2)],
      ["卡玛比率", fmtN(d.calmar || 0, 2)],
      ["系统获利指标 SQN", fmtN(d.sqn || 0, 2)],
      ["获利因子", fmtN(d.profit_factor || 0, 2)],
      [
        "交易期望值",
        `${fmtN(d.expectancy || 0, 2)} (${fmtN(d.expectancy_ratio || 0, 2)})`,
      ],
      ["", ""],
      ["最大账户回撤率", `${fmtN((d.max_drawdown_account || 0) * 100, 2)}%`],
      ["最大回撤额", `${fmtN(d.max_drawdown_abs || 0, 3)} U`],
      [
        "回撤开始 / 结束",
        `${d.drawdown_start || "-"} -> ${d.drawdown_end || "-"}`,
      ],
      [
        "回撤持时",
        d.drawdown_start && d.drawdown_end
          ? `${fmtN((new Date(d.drawdown_end) - new Date(d.drawdown_start)) / 86400000, 1)} 天`
          : "-",
      ],
      [
        "账户余额最小 / 最大值",
        `${fmtN(d.max_drawdown_low || 0, 2)} U / ${fmtN(d.final_balance > d.max_drawdown_high ? d.final_balance : d.max_drawdown_high || 0, 2)} U`,
      ],
      [
        "获利单 持仓最短/最长/平均",
        `${d.winner_holding_min || "-"} / ${d.winner_holding_max || "-"} / ${d.winner_holding_avg || "-"}`,
      ],
      [
        "亏损单 持仓最短/最长/平均",
        `${d.loser_holding_min || "-"} / ${d.loser_holding_max || "-"} / ${d.loser_holding_avg || "-"}`,
      ],
    ]);

    setNodeText(
      "report-snap-direction-count",
      `${d.trade_count_long || 0} / ${d.trade_count_short || 0}`,
    );
    setNodeText(
      "report-snap-direction-profit-pct",
      `${fmtSigned((d.profit_total_long || 0) * 100, 2, "%")} / ${fmtSigned((d.profit_total_short || 0) * 100, 2, "%")}`,
      `report-snapshot-value ${pos((d.profit_total_long || 0) + (d.profit_total_short || 0))}`,
    );
    setNodeText(
      "report-snap-direction-profit-abs",
      `${fmtSigned(d.profit_total_long_abs || 0, 3, " U")} / ${fmtSigned(d.profit_total_short_abs || 0, 3, " U")}`,
      `report-snapshot-value ${pos((d.profit_total_long_abs || 0) + (d.profit_total_short_abs || 0))}`,
    );
    setNodeText(
      "report-snap-avg-stake",
      `${fmtN(d.avg_stake_amount || 0, 3)} U`,
    );
    setNodeText(
      "report-snap-best-pair",
      d.best_pair?.key
        ? `${d.best_pair.key} ${fmtSigned(d.best_pair.profit_total_abs || 0, 2, " U")}`
        : "-",
      `report-snapshot-value ${pos(d.best_pair?.profit_total_abs || 0)}`,
    );
    setNodeText(
      "report-snap-worst-pair",
      d.worst_pair?.key
        ? `${d.worst_pair.key} ${fmtSigned(d.worst_pair.profit_total_abs || 0, 2, " U")}`
        : "-",
      `report-snapshot-value ${pos(d.worst_pair?.profit_total_abs || 0)}`,
    );

    const trades = d.trades || [];
    const bestTrade = trades.length
      ? trades.reduce((best, trade) =>
          (trade.profit_ratio || 0) > (best.profit_ratio || 0) ? trade : best,
        )
      : null;
    const worstTrade = trades.length
      ? trades.reduce((worst, trade) =>
          (trade.profit_ratio || 0) < (worst.profit_ratio || 0) ? trade : worst,
        )
      : null;
    setNodeText(
      "report-snap-best-worst-trade",
      bestTrade && worstTrade
        ? `${bestTrade.pair} ${fmtSigned((bestTrade.profit_ratio || 0) * 100, 2, "%")} / ${worstTrade.pair} ${fmtSigned((worstTrade.profit_ratio || 0) * 100, 2, "%")}`
        : "-",
    );

    const warningEl = document.getElementById("report-warning");
    if (warningEl) {
      if (d.sample_warning) {
        warningEl.textContent = d.sample_warning;
        warningEl.classList.remove("d-none");
      } else {
        warningEl.textContent = "";
        warningEl.classList.add("d-none");
      }
    }
  }

  async function runReport() {
    initReportGrid();
    const btn = document.getElementById("btn-report");
    if (btn) btn.disabled = true;

    // 【核心修复】获取当前界面上的金额
    const balanceInput = document.getElementById("balance-input");
    const balance = balanceInput ? balanceInput.value : "";

    const logCard = document.getElementById("report-log-widget");
    const logBox = document.getElementById("report-grid-log-box");
    const logBody = document.getElementById("report-log-body");
    if (logCard) logCard.style.display = "";
    if (logBody) logBody.style.display = "";
    if (logBox)
      logBox.textContent = `正在启动分析 (金额: ${balance || "默认"})...\n`;
    syncReportLogTargets();

    setStatus("sp-report", "running", "运行中...");

    try {
      // 通过 URL 参数发送余额，强制覆盖后端所有缓存
      await fetch(`/api/live-report/run?starting_balance=${balance}`, {
        method: "POST",
      });
      _reportPoll = setInterval(async () => {
        const s = await fetch("/api/live-report/status").then((r) => r.json());
        if (s.log && logBox) logBox.textContent = s.log;
        syncReportLogTargets();

        const statusMap = { running: "运行中...", ok: "已完成", error: "错误" };
        setStatus("sp-report", s.status, statusMap[s.status] || s.status);

        if (s.status !== "running") {
          clearInterval(_reportPoll);
          if (btn) btn.disabled = false;
          if (s.status === "ok") loadReportData();
        }
      }, 1500);
    } catch (e) {
      if (btn) btn.disabled = false;
      setStatus("sp-report", "error", "分析启动失败");
    }
  }

  async function loadReportData() {
    try {
      initReportGrid();
      const d = await fetch("/api/live-report/data").then((r) => r.json());
      if (d.status === "ok" && d.data) {
        setStatus("sp-report", "ok", "已完成");
        const timeEl = document.getElementById("report-time");
        if (d.updated_at && timeEl)
          timeEl.textContent = "更新: " + d.updated_at;
        renderReportView(d.data);
      } else {
        setStatus(
          "sp-report",
          d.status || "idle",
          d.status === "running" ? "运行中..." : "未运行",
        );
      }
    } catch (e) {
      console.error("Report load error", e);
      setStatus("sp-report", "error", "报告加载失败");
    }
  }

  function renderReportView(d) {
    initReportGrid();
    const meta1 = document.getElementById("report-main-meta");
    if (meta1)
      meta1.textContent = `实盘运行时间：${d.backtest_start || "-"} -> ${d.backtest_end || "-"}`;

    resetReportSectionState();
    renderTopKpis(d);
    renderSummaryBlocks(d);

    renderAlignedStatsTable(
      "report-pair-body",
      d.results_per_pair || [],
      "key",
      "pair",
    );
    renderAlignedStatsTable(
      "report-open-body",
      d.left_open_trades || [],
      "key",
      "open",
    );
    renderAlignedStatsTable(
      "report-enter-tag-body",
      d.results_per_enter_tag || [],
      "key",
      "enterTag",
    );
    renderAlignedStatsTable(
      "report-exit-reason-body",
      d.exit_reason_summary || [],
      "key",
      "exitReason",
    );
    renderMixTagStatsTable(
      "report-mix-tag-body",
      d.mix_tag_stats || [],
      "mixTag",
    );
    renderEquityChart(d);
    syncReportLogTargets();

    // 确保日志卡片在报告渲染后保持可见（clearAllPageData 可能已隐藏它）
    const logWidget = document.getElementById("report-log-widget");
    if (logWidget) logWidget.style.display = "";

    queueReportGridRefresh();
    // grid-stack 布局稳定后，强制图表重新计算尺寸
    requestAnimationFrame(() => {
      if (_equityChart) _equityChart.resize();
    });
  }

  async function loadCompareData() {
    try {
      initCompareGrid();
      await loadBacktestMeta();
      const body = await fetch("/api/backtest/compare-analysis").then((r) =>
        r.json(),
      );
      if (!body.ready) {
        resetCompareDrilldown();
        setCompareStatus("等待数据", "warning");
        setCompareMeta("需要实盘报告与回测结果");
        setCompareScore("-");
        setCompareDiagnosis(
          body.message ||
            "当前无法生成对比诊断，通常是因为实盘报告尚未生成，或回测结果尚未上传。",
        );
        setCompareNoteStatus("实盘或回测数据尚未就绪");
        setCompareNoteMeta(
          body.message || "请先生成实盘报告，并上传回测结果文件。",
        );
        const limitEl = document.getElementById("compare-limitations");
        if (limitEl)
          limitEl.textContent = body.diagnosis?.limitations || body.message;
        setCompareMatchCount(0);
        renderCompareOverviewCards([]);
        renderCompareContributionRows();
        renderCompareClusterRows();
        renderCompareAnomalyRows();
        renderCompareUnmatchedRows("compare-bt-only-body");
        renderCompareUnmatchedRows("compare-live-only-body");
        renderCompareRows();
        syncCompareWidgetHeights(body);
        return;
      }
      setCompareStatus("对比完成", "success");
      setCompareMeta(buildCompareScopeText(body));
      setCompareScore(body.diagnosis?.score ?? "-");
      setCompareMatchCount(
        body.overview?.matched_count || body.matching?.matched?.length || 0,
      );
      setCompareDiagnosis(
        body.diagnosis?.conclusion || "回测与实盘对比已完成。",
      );
      setCompareNoteStatus(
        `诊断分数 ${body.diagnosis?.score ?? "-"}，可继续按筛选下钻查看逐笔差异。`,
      );
      setCompareNoteMeta(buildCompareScopeText(body));
      COMPARE_STATE.raw = body;
      populateCompareFilterOptions(body.matching?.matched || []);
      updateCompareDrilldown();
      const limitEl = document.getElementById("compare-limitations");
      if (limitEl) {
        limitEl.textContent =
          body.diagnosis?.limitations ||
          "当前结果已经包含逐笔配对，但仍属于基于成交结果的准归因。";
      }
      renderCompareOverviewCards(body.overview?.cards || []);
      renderCompareContributionRows(body.attribution?.contributions || []);
      renderCompareClusterRows(body.attribution?.clusters || []);
      renderCompareAnomalyRows(body.matching?.top_anomalies || []);
      renderCompareUnmatchedRows(
        "compare-bt-only-body",
        body.matching?.bt_only || [],
      );
      renderCompareUnmatchedRows(
        "compare-live-only-body",
        body.matching?.live_only || [],
      );
      renderCompareRows(body.overview?.metrics || []);
      syncCompareWidgetHeights(body);
    } catch (e) {
      console.error("Compare load error", e);
      resetCompareDrilldown();
      setCompareStatus("回测对比加载失败", "danger");
      setCompareMeta("接口请求失败");
      setCompareScore("-");
      setCompareMatchCount(0);
      setCompareDiagnosis(
        "对比接口请求失败，请确认后端服务和对比数据准备状态。",
      );
      setCompareNoteStatus("接口请求失败");
      setCompareNoteMeta("请检查后端服务、实盘报告与回测上传状态。");
      const limitEl = document.getElementById("compare-limitations");
      if (limitEl) limitEl.textContent = "对比接口请求失败，未能生成逐笔归因。";
      renderCompareOverviewCards([]);
      renderCompareContributionRows();
      renderCompareClusterRows();
      renderCompareAnomalyRows();
      renderCompareUnmatchedRows("compare-bt-only-body");
      renderCompareUnmatchedRows("compare-live-only-body");
      renderCompareRows();
      syncCompareWidgetHeights(null);
    }
  }

  async function handleBacktestUpload(input) {
    const file = input?.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    setCompareStatus("正在上传回测文件", "info");
    setCompareMeta(file.name);
    setCompareNoteStatus("正在写入回测结果缓存");
    setCompareNoteMeta(`文件: ${file.name}`);

    try {
      const res = await fetch("/api/backtest/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || "上传失败");
      }

      setCompareStatus("回测文件已上传", "info");
      setCompareMeta(file.name);
      setCompareNoteStatus("回测结果已写入，可等待实盘报告或直接刷新对比");
      setCompareNoteMeta(`文件: ${file.name}`);
      setCompareFileName(file.name);
      await loadCompareData();
    } catch (e) {
      console.error("Upload backtest error", e);
      setCompareStatus(`上传失败: ${e.message}`, "danger");
      setCompareMeta("上传未完成");
      setCompareScore("-");
      setCompareDiagnosis(
        "回测文件上传失败，请检查文件格式是否为 freqtrade 导出的 JSON 或 ZIP。",
      );
      setCompareNoteStatus("回测文件上传失败");
      setCompareNoteMeta("请检查文件格式和服务日志。");
      renderCompareRows();
    } finally {
      input.value = "";
    }
  }

  function changeReportSectionPage(sectionKey, step) {
    const state = REPORT_SECTION_STATE[sectionKey];
    const rows = REPORT_SECTION_DATA[sectionKey] || [];
    const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    state.page = Math.min(totalPages, Math.max(1, state.page + step));
    state.expanded = false;
    rerenderReportSection(sectionKey);
  }

  function toggleReportSection(sectionKey) {
    const state = REPORT_SECTION_STATE[sectionKey];
    state.expanded = !state.expanded;
    if (!state.expanded) state.page = 1;
    rerenderReportSection(sectionKey);
  }

  function rerenderReportSection(sectionKey) {
    const rows = REPORT_SECTION_DATA[sectionKey] || [];
    if (sectionKey === "pair")
      return renderAlignedStatsTable("report-pair-body", rows, "key", "pair");
    if (sectionKey === "open")
      return renderAlignedStatsTable("report-open-body", rows, "key", "open");
    if (sectionKey === "enterTag")
      return renderAlignedStatsTable(
        "report-enter-tag-body",
        rows,
        "key",
        "enterTag",
      );
    if (sectionKey === "exitReason")
      return renderAlignedStatsTable(
        "report-exit-reason-body",
        rows,
        "key",
        "exitReason",
      );
    if (sectionKey === "mixTag")
      return renderMixTagStatsTable("report-mix-tag-body", rows, "mixTag");
  }

  // Export
  window.resetReportLayout = function resetReportLayout() {
    initReportGrid();
    localStorage.removeItem(REPORT_LAYOUT_KEY);
    applyReportLayout(REPORT_DEFAULT_LAYOUT);
    setReportLayoutStatus("已恢复默认布局", "info");
  };
  window.resetCompareLayout = function resetCompareLayout() {
    initCompareGrid();
    localStorage.removeItem(COMPARE_LAYOUT_KEY);
    applyCompareLayout(COMPARE_DEFAULT_LAYOUT);
    setCompareLayoutStatus("已恢复默认布局", "info");
  };
  window.runReport = runReport;
  window.loadReportData = loadReportData;
  window.handleBacktestUpload = handleBacktestUpload;
  window.loadCompareData = loadCompareData;
  window.setCompareFilter = function setCompareFilter(key, value) {
    if (!(key in COMPARE_STATE.filters)) return;
    COMPARE_STATE.filters[key] = value || "";
    updateCompareDrilldown();
  };
  window.resetCompareFilters = function resetCompareFilters() {
    COMPARE_STATE.filters = {
      pair: "",
      enterTag: "",
      side: "",
      bucket: "",
      exitReason: "",
    };
    const map = {
      pair: "compare-filter-pair",
      enterTag: "compare-filter-tag",
      side: "compare-filter-side",
      bucket: "compare-filter-bucket",
      exitReason: "compare-filter-exit-reason",
    };
    Object.entries(map).forEach(([key, id]) => {
      const el = document.getElementById(id);
      if (el) el.value = COMPARE_STATE.filters[key] || "";
    });
    updateCompareDrilldown();
  };
  window.setCompareGroupBy = function setCompareGroupBy(value) {
    COMPARE_STATE.groupBy = value || "pair";
    updateCompareDrilldown();
  };
  window.setCompareTableLimit = function setCompareTableLimit(stateKey, limit) {
    if (!(stateKey in COMPARE_STATE.limits)) return;
    COMPARE_STATE.limits[stateKey] = Number(limit) || 20;
    if (stateKey === "breakdown" || stateKey === "matched") {
      updateCompareDrilldown();
      return;
    }
    if (stateKey === "anomalies") {
      renderCompareAnomalyRows(
        COMPARE_STATE.raw?.matching?.top_anomalies || [],
      );
      return;
    }
    if (stateKey === "btOnly") {
      renderCompareUnmatchedRows(
        "compare-bt-only-body",
        COMPARE_STATE.raw?.matching?.bt_only || [],
      );
      return;
    }
    if (stateKey === "liveOnly") {
      renderCompareUnmatchedRows(
        "compare-live-only-body",
        COMPARE_STATE.raw?.matching?.live_only || [],
      );
    }
  };
  window.changeReportSectionPage = changeReportSectionPage;
  window.toggleReportSection = toggleReportSection;
  window.toggleReportLog = toggleReportLog;
})();
