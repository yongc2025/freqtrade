/**
 * Closed Trades (History) Page Logic
 */

(function () {
  let _tradesData = [];
  let _tradePage = 1;
  let _tradePageSize = 10;
  let _tradeSort = { col: null, dir: 1 };

  async function initTradeFilters() {
    try {
      const d = await fetch("/api/trades/filters").then((r) => r.json());
      const rs = document.getElementById("tf-reason");
      const ts = document.getElementById("tf-tag");
      if (rs) (d.exit_reasons || []).forEach((v) => rs.add(new Option(v, v)));
      if (ts) (d.enter_tags || []).forEach((v) => ts.add(new Option(v, v)));
    } catch (e) {
      console.error("Failed to load filters", e);
    }
  }

  async function loadTrades() {
    const p = new URLSearchParams();
    const g = (id, key) => {
      const el = document.getElementById(id);
      const v = el ? el.value.trim() : "";
      if (v) p.append(key, v);
    };
    g("tf-pair", "pair");
    g("tf-reason", "exit_reason");
    g("tf-tag", "enter_tag");
    g("tf-dir", "is_short");
    g("tf-from", "date_from");
    g("tf-to", "date_to");
    g("tf-min-p", "min_profit");
    g("tf-max-p", "max_profit");

    try {
      const d = await fetch("/api/trades?" + p).then((r) => r.json());
      _tradesData = d.trades || [];
      _tradePage = 1;
      renderTradeStats(d.stats || {});
      renderTradeTable(_tradesData);
    } catch (e) {
      console.error("Failed to load trades", e);
    }
  }

  function renderTradeStats(s) {
    const pnl = s.total_pnl || 0;

    const setVal = (id, val, color) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = val;
      if (color !== undefined)
        el.className = "value " + (color >= 0 ? "profit-up" : "profit-down");
    };

    setVal("ts-total", s.total || "-");
    setVal("ts-pnl", (pnl >= 0 ? "+" : "") + fmtN(pnl) + " U", pnl);
    setVal("ts-wr", s.winrate ? s.winrate.toFixed(1) + "%" : "-");
    setVal("ts-avg", fmtPct(s.avg_profit_pct), s.avg_profit_pct || 0);

    const countEl = document.getElementById("trade-count");
    if (countEl) countEl.textContent = `${s.total || 0} 笔`;

    const foot = document.getElementById("trades-footer");
    if (foot) {
      foot.textContent = `${s.total || 0} 笔交易 | 胜率 ${s.winrate || 0}% | 平均收益 ${fmtN(s.avg_profit_pct || 0)}% | 总盈亏 ${(pnl >= 0 ? "+" : "") + fmtN(pnl)} U`;
    }
  }

  function renderTradeTable(trades) {
    const tbody = document.getElementById("trades-tbody");
    if (!tbody) return;
    if (!trades.length) {
      tbody.innerHTML =
        '<tr><td colspan="12" class="text-center py-3 text-muted">无数据</td></tr>';
      updateTradePagination(0);
      return;
    }

    const sortedTrades = [...trades].sort((left, right) => {
      if (!_tradeSort.col) return 0;
      const leftVal = getTradeSortValue(left, _tradeSort.col);
      const rightVal = getTradeSortValue(right, _tradeSort.col);

      if (typeof leftVal === "string" || typeof rightVal === "string") {
        return String(leftVal).localeCompare(String(rightVal)) * _tradeSort.dir;
      }

      return (leftVal - rightVal) * _tradeSort.dir;
    });

    const totalPages = Math.max(
      1,
      Math.ceil(sortedTrades.length / _tradePageSize),
    );
    if (_tradePage > totalPages) _tradePage = totalPages;
    const start = (_tradePage - 1) * _tradePageSize;
    const pageRows = sortedTrades.slice(start, start + _tradePageSize);

    const fmtPrice = (v) => (v < 1 ? v.toFixed(6) : v.toFixed(4));

    tbody.innerHTML = pageRows
      .map((t) => {
        const dir = t.is_short
          ? '<span class="text-danger">空</span>'
          : '<span class="text-success">多</span>';
        const pc = t.profit_abs >= 0 ? "profit-up" : "profit-down";
        return `<tr>
          <td class="text-muted small">${t.id}</td>
          <td class="fw-bold">${t.pair.replace(":USDT", "")}</td>
          <td>${dir}</td>
          <td class="small">${(t.open_date || "").slice(5, 16)}</td>
          <td class="small">${(t.close_date || "").slice(5, 16)}</td>
          <td class="text-muted">${fmtN(t.stake_amount, 1)}</td>
          <td class="text-muted">${fmtPrice(t.open_rate)}</td>
          <td class="text-muted">${fmtPrice(t.close_rate)}</td>
          <td class="${pc}">${t.profit_abs >= 0 ? "+" : ""}${fmtN(t.profit_abs)}</td>
          <td class="${pc}">${t.profit_ratio >= 0 ? "+" : ""}${fmtN(t.profit_ratio)}%</td>
          <td><span class="badge bg-secondary opacity-75 small">${t.exit_reason || "-"}</span></td>
          <td><span class="badge bg-info opacity-75 small text-dark">${t.enter_tag || "-"}</span></td>
        </tr>`;
      })
      .join("");

    updateTradePagination(sortedTrades.length);
  }

  function getTradeSortValue(trade, column) {
    if (column === "open_date" || column === "close_date") {
      const ts = Date.parse(trade[column] || "");
      return Number.isNaN(ts) ? 0 : ts;
    }

    if (column === "profit_abs" || column === "profit_ratio") {
      return Number(trade[column] || 0);
    }

    return trade[column] ?? 0;
  }

  function sortTradesBy(column) {
    _tradeSort.dir = _tradeSort.col === column ? -_tradeSort.dir : 1;
    _tradeSort.col = column;
    _tradePage = 1;

    document.querySelectorAll("#page-trades th.sortable").forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.getAttribute("onclick")?.includes(`'${column}'`)) {
        th.classList.add(_tradeSort.dir === 1 ? "sort-asc" : "sort-desc");
      }
    });

    renderTradeTable(_tradesData);
  }

  function updateTradePagination(total) {
    const totalPages = Math.max(1, Math.ceil(total / _tradePageSize));
    const infoEl = document.getElementById("trades-page-info");
    const prevBtn = document.getElementById("trades-prev-btn");
    const nextBtn = document.getElementById("trades-next-btn");
    if (infoEl) {
      if (!total) {
        infoEl.textContent = "第 0 / 0 页";
      } else {
        const start = (_tradePage - 1) * _tradePageSize + 1;
        const end = Math.min(_tradePage * _tradePageSize, total);
        infoEl.textContent = `第 ${_tradePage} / ${totalPages} 页，显示 ${start}-${end} / ${total}`;
      }
    }
    if (prevBtn) prevBtn.disabled = !total || _tradePage <= 1;
    if (nextBtn) nextBtn.disabled = !total || _tradePage >= totalPages;
  }

  function changeTradesPage(step) {
    const totalPages = Math.max(
      1,
      Math.ceil(_tradesData.length / _tradePageSize),
    );
    _tradePage = Math.min(totalPages, Math.max(1, _tradePage + step));
    renderTradeTable(_tradesData);
  }

  function changeTradesPageSize(size) {
    _tradePageSize = Math.max(1, Number(size) || 10);
    _tradePage = 1;
    renderTradeTable(_tradesData);
  }

  function resetTradeF() {
    ["tf-pair", "tf-from", "tf-to", "tf-min-p", "tf-max-p"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    ["tf-reason", "tf-tag", "tf-dir"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.selectedIndex = 0;
    });
    loadTrades();
  }

  // Export
  window.loadTrades = loadTrades;
  window.initTradeFilters = initTradeFilters;
  window.resetTradeF = resetTradeF;
  window.changeTradesPage = changeTradesPage;
  window.changeTradesPageSize = changeTradesPageSize;
  window.sortTradesBy = sortTradesBy;
})();
