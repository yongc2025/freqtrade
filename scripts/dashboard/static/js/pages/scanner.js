/**
 * Market Scanner Page Logic
 */

(function () {
  let _scanData = [];
  let _scanSort = { col: "volume_rank_3d", dir: 1 };
  let _scanPoll = null;
  let _scanWarnTimer = null;

  function setScanButton(isRunning, label) {
    const btn = document.getElementById("btn-scan");
    if (!btn) return;
    btn.disabled = isRunning;
    btn.textContent = label;
  }

  function stopScanPolling() {
    if (_scanPoll) {
      clearInterval(_scanPoll);
      _scanPoll = null;
    }
    if (_scanWarnTimer) {
      clearTimeout(_scanWarnTimer);
      _scanWarnTimer = null;
    }
  }

  async function loadScanData() {
    try {
      const d = await fetch("/api/market-scan").then((r) => r.json());
      updateScanStatus(d);
      _scanData = d.data || [];
      renderScan();
      if (d.status === "running") {
        setScanButton(true, "扫描中...");
      }
    } catch (e) {
      console.error("Failed to load scan data", e);
      setStatus("sp-scan", "error", "加载失败");
    }
  }

  async function refreshScan() {
    stopScanPolling();
    setScanButton(true, "扫描中...");
    setStatus("sp-scan", "running", "已触发扫描");
    const timeEl = document.getElementById("scan-time");
    if (timeEl) timeEl.textContent = "通常需要 20-60 秒，请稍候";

    try {
      await fetch("/api/market-scan/refresh", { method: "POST" });

      _scanWarnTimer = setTimeout(() => {
        setStatus("sp-scan", "warning", "扫描仍在运行");
        const warnTime = document.getElementById("scan-time");
        if (warnTime) warnTime.textContent = "Binance 拉取较慢，继续等待即可";
      }, 15000);

      _scanPoll = setInterval(async () => {
        const d = await fetch("/api/market-scan").then((r) => r.json());
        updateScanStatus(d);
        if (d.status !== "running") {
          stopScanPolling();
          setScanButton(false, "确认刷新");
          _scanData = d.data || [];
          renderScan();
        }
      }, 2000);
    } catch (e) {
      stopScanPolling();
      setScanButton(false, "确认刷新");
      setStatus("sp-scan", "error", "请求失败");
    }
  }

  function updateScanStatus(d) {
    const map = {
      idle: ["idle", "空闲"],
      running: ["running", "扫描中..."],
      ok: ["ok", `已更新 ${d.count || (d.data || []).length} 个币种`],
      error: ["error", d.error || "扫描失败"],
    };
    const [cls, txt] = map[d.status] || ["idle", d.status];
    setStatus("sp-scan", cls, txt);
    const timeEl = document.getElementById("scan-time");
    if (d.updated_at && timeEl) timeEl.textContent = "更新: " + d.updated_at;
    if (d.status === "running") {
      setScanButton(true, "扫描中...");
    }
  }

  function filteredScanData() {
    const q = document.getElementById("sf-search")?.value.toLowerCase() || "";
    const minC = parseFloat(document.getElementById("sf-min-chg")?.value);
    const maxC = parseFloat(document.getElementById("sf-max-chg")?.value);
    const age = document.getElementById("sf-age")?.value;

    return _scanData
      .filter((r) => {
        if (q && !r.display.toLowerCase().includes(q)) return false;
        if (!isNaN(minC) && r.price_change_3d < minC) return false;
        if (!isNaN(maxC) && r.price_change_3d > maxC) return false;
        if (age === "ok" && !r.age_ok) return false;
        return true;
      })
      .sort((a, b) => {
        const va = a[_scanSort.col] ?? 0;
        const vb = b[_scanSort.col] ?? 0;
        return typeof va === "string"
          ? va.localeCompare(vb) * _scanSort.dir
          : (va - vb) * _scanSort.dir;
      });
  }

  function renderScan() {
    const data = filteredScanData();
    const tbody = document.getElementById("scan-tbody");
    if (!tbody) return;

    if (!data.length) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="text-center py-4 text-light-muted">当前无扫描结果。点击“确认刷新”后会开始拉取 Binance 合约数据。</td></tr>';
      const countEl = document.getElementById("scan-count");
      if (countEl) countEl.textContent = "0 个币种";
      return;
    }

    const fmtPrice = (v) => (v < 1 ? v.toFixed(6) : v.toFixed(4));
    const fmtVol = (v) => {
      const value = Number(v || 0);
      const absValue = Math.abs(value);
      if (absValue >= 1_000_000_000)
        return (value / 1_000_000_000).toFixed(2) + "B";
      if (absValue >= 1_000_000) return (value / 1_000_000).toFixed(2) + "M";
      if (absValue >= 1_000) return (value / 1_000).toFixed(2) + "K";
      return value.toFixed(2);
    };
    const pos = (v) => (v >= 0 ? "profit-up" : "profit-down");

    tbody.innerHTML = data
      .map(
        (r) => `
    <tr>
      <td><b class="text-primary">#${r.volume_rank_3d}</b></td>
      <td class="fw-bold">${r.display}</td>
      <td>${fmtPrice(r.last_price)}</td>
      <td class="${pos(r.price_change_3d)}">${r.price_change_3d >= 0 ? "+" : ""}${r.price_change_3d.toFixed(2)}%</td>
      <td>${fmtVol(r.volume_24h)}</td>
      <td>${fmtVol(r.volume_3d_quote)}${r.vol_3d_estimated ? '<span title="估算量" class="text-warning ms-1">~</span>' : ""}</td>
      <td class="text-muted">#${r.volume_rank_overall}</td>
      <td class="${r.age_ok ? "" : "text-danger"}">${r.age_days != null ? r.age_days + "d" : "-"}</td>
    </tr>`,
      )
      .join("");

    const countEl = document.getElementById("scan-count");
    if (countEl)
      countEl.textContent = `显示 ${data.length} / ${_scanData.length} 个币种`;
  }

  function exportScanData() {
    const data = filteredScanData();
    if (!data.length) {
      setStatus("sp-scan", "warning", "无可导出结果");
      return;
    }

    const csvRows = ["排名,币种"];
    data.forEach((row) => {
      const pair = String(row.symbol || row.display || "").replace(/"/g, '""');
      csvRows.push(`${row.volume_rank_3d},"${pair}"`);
    });

    const csv = "\ufeff" + csvRows.join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const ts = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
    link.href = url;
    link.download = `market_scan_${ts}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setStatus("sp-scan", "ok", `已导出 ${data.length} 条结果`);
  }

  function sortScanBy(col) {
    _scanSort.dir = _scanSort.col === col ? -_scanSort.dir : 1;
    _scanSort.col = col;

    // UI Feedback for sort
    document.querySelectorAll("#page-scan th.sortable").forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.getAttribute("onclick")?.includes(`'${col}'`)) {
        th.classList.add(_scanSort.dir === 1 ? "sort-asc" : "sort-desc");
      }
    });
    renderScan();
  }

  // Export functions to window
  window.loadScanData = loadScanData;
  window.refreshScan = refreshScan;
  window.sortScanBy = sortScanBy;
  window.renderScan = renderScan;
  window.exportScanData = exportScanData;
})();
