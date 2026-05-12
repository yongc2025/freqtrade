"""
==========================================================================
batch_compare.py — 单策略十四阶段周期回测分析脚本
==========================================================================

功能:
  1. 对指定策略批量运行 6 个加密货币市场明确周期的回测
  2. 自动提取核心量化指标 (Sharpe/Sortino/Calmar/回撤/胜率/利润/出场分解)
  3. 对每个周期输出优势/劣势评估 (强项 + 弱项)
  4. 终端输出详细报告 + 生成 HTML 可视化报告

用法:
  # ① 完整十四阶段分析（最常用，依次回测全部14个周期，生成终端报告 + HTML）
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5

  # ② 只跑指定阶段（节省时间，可选阶段 key 见下方 PHASES 定义）
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5 --phases bull_2021q1 luna_crisis etf_halving tariff_shock

  # ③ 预览模式（只打印将要执行的命令，不实际运行回测，用于确认参数）
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5 --dry-run

  # ④ 从已有 JSON 重新生成报告（跳过耗时回测，直接刷新 HTML，用于调整样式或修复指标后复用数据）
  conda activate freqAi ; python scripts/batch_compare.py --from-json user_data/bt_extracted/phase_analysis_xxx.json
==========================================================================
"""

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

# ─── 十一大市场周期定义 ───────────────────────────────────────────────────────
PHASES = {
    # ── 2021 牛市 ──────────────────────────────────────────────────────────────
    "bull_2021q1": {
        "range":       "20210101-20210430",
        "label":       "①机构牛市",
        "description": "MicroStrategy/Tesla买入BTC，Coinbase上市，机构资金蜂拥入场，山寨全面爆发",
        "market":      "强势单边上涨",
        "btc_change":  "+121%",
    },
    "crash_china": {
        "range":       "20210501-20210731",
        "label":       "②矿难政策崩盘",
        "description": "中国关停矿场政策冲击，BTC单月腰斩，高波动急速下跌，做多陷阱密集",
        "market":      "政策黑天鹅崩跌",
        "btc_change":  "-53%",
    },
    "bull_2021ath": {
        "range":       "20210801-20211130",
        "label":       "③牛市历史新高",
        "description": "BTC反弹创历史新高69K，ETH生态爆发，NFT/DeFi狂潮，牛市最后疯狂",
        "market":      "牛市顶峰疯狂",
        "btc_change":  "+64%",
    },
    # ── 2022 双重黑天鹅熊市 ───────────────────────────────────────────────────
    "bear_orderly": {
        "range":       "20211201-20220430",
        "label":       "④熊市有序下跌",
        "description": "美联储加息预期发酵，无重大黑天鹅，市场有序去杠杆下跌，BTC 69K→38K",
        "market":      "常规宏观熊市",
        "btc_change":  "-44%",
    },
    "luna_crisis": {
        "range":       "20220501-20220930",
        "label":       "⑤Terra/Luna崩盘",
        "description": "史上最大DeFi黑天鹅：UST脱锚→LUNA归零(5月)，三箭资本破产(6月)，BTC跌破20K",
        "market":      "DeFi系统性崩溃",
        "btc_change":  "-49%",
    },
    "ftx_bottom": {
        "range":       "20221001-20230131",
        "label":       "⑥FTX暴雷+熊底",
        "description": "全球第二大交易所FTX破产(11月)，BTC跌至15.5K历史低点，行业信任危机",
        "market":      "交易所黑天鹅+极恐",
        "btc_change":  "-20%",
    },
    # ── 2023 磨底+复苏 ────────────────────────────────────────────────────────
    "recovery": {
        "range":       "20230201-20231031",
        "label":       "⑦熊末磨底复苏",
        "description": "SVB银行危机引发USDC脱锚(3月)，BTC在低波动中缓慢筑底复苏，情绪修复",
        "market":      "低波动缓慢复苏",
        "btc_change":  "+52%",
    },
    # ── 2024 结构性牛市 ───────────────────────────────────────────────────────
    "etf_halving": {
        "range":       "20231101-20240630",
        "label":       "⑧ETF获批+减半",
        "description": "比特币现货ETF获批(2024-01-10)BTC突破前高至73K，第四次减半(4月20日)",
        "market":      "结构性催化剂牛市",
        "btc_change":  "+106%",
    },
    "election_bull": {
        "range":       "20240701-20241231",
        "label":       "⑨大选牛市冲顶",
        "description": "特朗普加密友好政策胜选(11月5日)，BTC从60K暴涨至历史新高108K，极速单边",
        "market":      "政策驱动暴涨",
        "btc_change":  "+80%",
    },
    # ── 2025 后泡沫调整 ───────────────────────────────────────────────────────
    "correction_2025": {
        "range":       "20250101-20250401",
        "label":       "⑩就职后高位回调",
        "description": "特朗普就职(1月20日)后宏观预期落地，BTC高位震荡下行，资金获利了结",
        "market":      "高位震荡回调",
        "btc_change":  "-13%",
    },
    "tariff_shock": {
        "range":       "20250402-20250630",
        "label":       "⑪关税危机急跌",
        "description": "Liberation Day关税冲击(4月2日)BTC急跌至74K，市场极度恐慌，90天暂停缓和",
        "market":      "外部冲击极恐",
        "btc_change":  "-10%",
    },
    "btc_ath_2025": {
        "range":       "20250701-20251031",
        "label":       "⑫BTC新高震荡117K",
        "description": "BTC突破前高在109K-117K高位震荡，持续强势但已无新高突破动能，市场分歧加大",
        "market":      "高位横盘震荡",
        "btc_change":  "+5%",
    },
    "btc_crash_2026": {
        "range":       "20251101-20260228",
        "label":       "⑬BTC崩跌65K熊市",
        "description": "11月加速下跌(104K→86K)，12月-1月死猫跳(88K-93K)，2月再崩至65K，系统性熊市",
        "market":      "系统性熊市崩跌",
        "btc_change":  "-45%",
    },
    "btc_recovery_2026": {
        "range":       "20260301-20260419",
        "label":       "⑭熊底反弹尝试75K",
        "description": "BTC从65K低点反弹至75K，当前阶段，方向未明：熊市反弹 or 新一轮牛市起点",
        "market":      "底部反弹/方向待定",
        "btc_change":  "+15%",
    },
}

OUTPUT_DIR = Path("user_data/bt_extracted")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_OUTPUT_FILE = OUTPUT_DIR / "_tmp_bt_output.txt"


# ─── BTC 本地 K 线工具 ────────────────────────────────────────────────────────
def _find_btc_feather(config_path=None):
    """查找本地 BTC/USDT 1h feather 文件，返回 Path 或 None。"""
    candidates = []
    if config_path:
        try:
            with open(config_path, encoding="utf-8") as _f:
                _cfg = json.load(_f)
            _exch = _cfg.get("exchange", {}).get("name", "binance").lower()
            _udd  = Path(_cfg.get("user_data_dir", "user_data"))
            _tm   = _cfg.get("trading_mode", "futures")
            if _tm == "futures":
                candidates.append(_udd / "data" / _exch / "futures" / "BTC_USDT_USDT-1h-futures.feather")
            else:
                candidates.append(_udd / "data" / _exch / "BTC_USDT-1h.feather")
        except Exception:
            pass
    # 默认回退路径
    candidates += [
        Path("user_data/data/binance/futures/BTC_USDT_USDT-1h-futures.feather"),
        Path("user_data/data/binance/BTC_USDT-1h.feather"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_btc_df(config_path=None):
    """加载 BTC/USDT 1h K线 DataFrame，失败返回 None。"""
    try:
        import pandas as _pd
    except ImportError:
        return None
    fp = _find_btc_feather(config_path)
    if fp is None:
        return None
    try:
        _df = _pd.read_feather(fp)
        if not hasattr(_df["date"].dtype, "tz") or _df["date"].dtype.tz is None:
            _df["date"] = _pd.to_datetime(_df["date"], utc=True)
        return _df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _btc_pct_from_range(df, range_str):
    """
    计算 BTC 在给定时段的精确涨跌幅。
    range_str 格式: "20210101-20210430"
    返回如 "+121.3%" 字符串，若数据不足则返回 None。
    """
    try:
        import pandas as _pd
        parts      = range_str.split("-")
        start_str, end_str = parts[0], parts[-1]
        start_dt = _pd.Timestamp(
            f"{start_str[:4]}-{start_str[4:6]}-{start_str[6:]}", tz="UTC"
        )
        end_dt = _pd.Timestamp(
            f"{end_str[:4]}-{end_str[4:6]}-{end_str[6:]}", tz="UTC"
        ) + _pd.Timedelta(days=1)   # 包含结束日全天
        seg = df[(df["date"] >= start_dt) & (df["date"] < end_dt)]
        if len(seg) < 2:
            return None
        pct  = (float(seg.iloc[-1]["close"]) / float(seg.iloc[0]["open"]) - 1) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"
    except Exception:
        return None


def check_btc_data(config_path, phase_keys):
    """
    检查 BTC K线对各阶段的覆盖情况。
    返回 (df_or_None, missing_list)
    missing_list 每项: {"phase": key, "range": str, "reason": str}
    """
    try:
        import pandas as _pd
    except ImportError:
        print("  ⚠ pandas 未安装，无法读取 BTC 本地数据，将使用估算值。")
        return None, []

    df = _load_btc_df(config_path)
    if df is None:
        fp = _find_btc_feather(config_path)
        print(f"\n  ⚠ 未找到 BTC K线文件，将使用内置估算值。")
        print(f"  ℹ 可用以下命令下载：")
        print(f"    conda activate freqAi ; freqtrade download-data "
              f"--config {config_path or 'user_data/config.json'} "
              f"--pairs BTC/USDT:USDT --timeframes 1h --timerange 20210101-\n")
        return None, []

    df_start = df["date"].min()
    df_end   = df["date"].max()
    missing  = []

    for pk in phase_keys:
        rng   = PHASES[pk]["range"]
        parts = rng.split("-")
        s, e  = parts[0], parts[-1]
        need_s = _pd.Timestamp(f"{s[:4]}-{s[4:6]}-{s[6:]}", tz="UTC")
        need_e = _pd.Timestamp(f"{e[:4]}-{e[4:6]}-{e[6:]}", tz="UTC")
        if need_s < df_start or need_e > df_end:
            missing.append({
                "phase": pk, "range": rng,
                "reason": (
                    f"本地数据覆盖 {df_start.strftime('%Y-%m-%d')} ~ "
                    f"{df_end.strftime('%Y-%m-%d')}，"
                    f"需要 {need_s.strftime('%Y-%m-%d')} ~ {need_e.strftime('%Y-%m-%d')}"
                ),
            })

    return df, missing


# ─── 指标提取器 ───────────────────────────────────────────────────────────────
def _find(pattern, text, default="N/A"):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else default


def _find_any(patterns, text, default="N/A"):
    """尝试多个 pattern，返回第一个匹配结果（用于中英文双重保障）"""
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return default


def extract_metrics(output):
    # freqtrade 表格使用 │ (U+2502) 作为列分隔符，而非 ASCII |
    # SEP 同时匹配两种字符以兼容未来版本
    S  = r"[│|]"          # 单个分隔符
    NS = r"[^│|]"         # 非分隔符字符
    return {
        # 交易次数: TOTAL 行第2列
        "trades": _find_any([
            S + r"\s*TOTAL\s*" + S + r"\s*(\d+)\s*" + S,
        ], output),
        # 总收益率: SUMMARY METRICS 区块 "总收益率 %" 行
        "total_profit_pct": _find_any([
            r"总收益率" + NS + r"*" + S + r"\s*([-\d.]+)%",
            r"(?:Total profit|Absolute Return)" + NS + r"*" + S + r"\s*([-\d.]+)%",
        ], output),
        "total_profit_usdt": _find_any([
            r"(?:净利润|Profit)" + NS + r"*\((?:绝对值|Absolute)\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"净利润" + NS + r"*" + S + r"\s*([-\d.]+)\s*USDT",
        ], output),
        "cagr_pct": _find_any([
            r"\(CAGR\)" + NS + r"*" + S + r"\s*([-\d.]+)%",
            r"CAGR" + NS + r"*" + S + r"\s*([-\d.]+)%",
        ], output),
        "sharpe": _find_any([
            r"\(Sharpe\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"Sharpe" + NS + r"*" + S + r"\s*([-\d.]+)",
        ], output),
        "sortino": _find_any([
            r"\(Sortino\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"Sortino" + NS + r"*" + S + r"\s*([-\d.]+)",
        ], output),
        "calmar": _find_any([
            r"\(Calmar\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"Calmar" + NS + r"*" + S + r"\s*([-\d.]+)",
        ], output),
        "sqn": _find_any([
            r"\(SQN\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"SQN" + NS + r"*" + S + r"\s*([-\d.]+)",
        ], output),
        "profit_factor": _find_any([
            r"\(Profit Factor\)" + NS + r"*" + S + r"\s*([-\d.]+)",
            r"Profit Factor" + NS + r"*" + S + r"\s*([-\d.]+)",
        ], output),
        "expectancy": _find_any([
            r"\(Ratio\)" + NS + r"*" + S + r"\s*([-\d.()]+)",
            r"Expectancy" + NS + r"*" + S + r"\s*([-\d.()]+)",
        ], output),
        "max_drawdown_pct": _find_any([
            r"\(Underwater\)" + NS + r"*" + S + r"\s*([-\d.]+)%",
            r"Underwater" + NS + r"*" + S + r"\s*([-\d.]+)%",
            r"Max drawdown" + NS + r"*" + S + r"\s*([-\d.]+)%",
        ], output),
        "drawdown_days": _find_any([
            r"(?:drawdown duration|回撤持时)" + NS + r"*" + S + r"\s*(\d+ days" + NS + r"*)",
        ], output),
        "market_change": _find_any([
            r"Market Change" + NS + r"*" + S + r"\s*([-\d.]+)%",
        ], output),
        "final_balance": _find_any([
            r"(?:Final balance|最终账户余额)" + NS + r"*" + S + r"\s*([\d.]+)",
        ], output),
        # 胜率: TOTAL 行末尾 Win Draw Loss Win% 列
        "win_rate": _find(
            S + r"\s*TOTAL\s*" + S + r"\s*\d+\s*" + S
            + r"\s*[-\d.]+\s*" + S + r"\s*[-\d.]+\s*" + S
            + r"\s*[-\d.]+\s*" + S + r"\s*" + NS + r"+\s*" + S
            + r"\s*\d+\s+\d+\s+\d+\s+([-\d.]+)\s*" + S,
            output,
        ),
        # Long/Short profit 行含纯 ASCII 关键词
        "long_profit_pct":  _find(
            r"Long\s*/\s*Short profit\s*%" + NS + r"*" + S + r"\s*([-\d.]+)%", output),
        "short_profit_pct": _find(
            r"Long\s*/\s*Short profit\s*%" + NS + r"*" + S + r"\s*[-\d.]+%\s*/\s*([-\d.]+)%", output),
    }


def extract_exit_breakdown(output):
    result = {}
    S = r"[│|]"

    def parse_exit(name, pattern):
        m = re.search(pattern, output)
        if m:
            result[name] = {
                "count":     m.group(1),
                "avg_pct":   m.group(2),
                "total_pct": m.group(3),
            }

    parse_exit("roi",       S + r"\s*roi\s*"                + S + r"\s*(\d+)\s*" + S + r"\s*([-\d.]+)\s*" + S + r"\s*[-\d.]+\s*" + S + r"\s*([-\d.]+)")
    parse_exit("stop_loss", S + r"\s*stop_loss\s*"          + S + r"\s*(\d+)\s*" + S + r"\s*([-\d.]+)\s*" + S + r"\s*[-\d.]+\s*" + S + r"\s*([-\d.]+)")
    parse_exit("mtm_long",  S + r"\s*momentum_exit_long\s*" + S + r"\s*(\d+)\s*" + S + r"\s*([-\d.]+)\s*" + S + r"\s*[-\d.]+\s*" + S + r"\s*([-\d.]+)")
    parse_exit("mtm_short", S + r"\s*momentum_exit_short\s*"+ S + r"\s*(\d+)\s*" + S + r"\s*([-\d.]+)\s*" + S + r"\s*[-\d.]+\s*" + S + r"\s*([-\d.]+)")
    return result


# ─── 单次回测运行器 ───────────────────────────────────────────────────────────
def run_backtest(config, strategy, phase_key, btc_df=None):
    phase = PHASES[phase_key]
    # 优先使用本地 K 线精确值，降级到手动估算值
    _live_btc = _btc_pct_from_range(btc_df, phase["range"]) if btc_df is not None else None
    btc_display = _live_btc or phase["btc_change"]
    btc_src     = "实时" if _live_btc else "估算"
    cmd = [
        "freqtrade", "backtesting",
        "--config", config,
        "--strategy", strategy,
        "--timerange", phase["range"],
    ]

    print(f"\n{'='*72}")
    print(f"  [{phase['label']}]  {phase['description']}")
    print(f"  时间段: {phase['range']}   市场: {phase['market']} (BTC {btc_display} [{btc_src}])")
    print(f"  命令: {' '.join(cmd)}")
    print(f"{'='*72}")

    try:
        # 用二进制模式捕获 subprocess 原始字节，避免 Windows 终端编码丢失
        with open(TMP_OUTPUT_FILE, "wb") as tmp:
            proc = subprocess.run(cmd, stdout=tmp, stderr=tmp, timeout=900)

        raw_bytes = TMP_OUTPUT_FILE.read_bytes()
        # freqtrade on Windows: TRADE 表格 (│ 分隔符) 用 UTF-8, SUMMARY METRICS 中文标签用 GBK
        # 双解码：UTF-8 用于交易表指标，GBK 用于 SUMMARY METRICS 中文字段
        output_utf8 = raw_bytes.decode("utf-8",  errors="replace")
        output_gbk  = raw_bytes.decode("gbk",    errors="replace")
        # 优先用 UTF-8 作为主输出（TOTAL 行 / 出场分解 等 ASCII 指标）
        output = output_utf8 if "TOTAL" in output_utf8 else output_gbk

        if proc.returncode != 0 and "Result for strategy" not in output and "TOTAL" not in output:
            print(f"  ✗ 回测失败 (exit={proc.returncode})")
            for line in output.split("\n")[-15:]:
                if line.strip():
                    print(f"    {line}")
            return {
                "phase": phase_key, "phase_label": phase["label"],
                "status": "FAILED", "error": output[-800:],
            }

        metrics = extract_metrics(output_utf8)
        exits   = extract_exit_breakdown(output_utf8)
        # 用 GBK 解码补全 N/A 指标（SUMMARY METRICS 中文字段）
        if output_gbk:
            metrics_gbk = extract_metrics(output_gbk)
            for k, v in metrics.items():
                if v == "N/A" and metrics_gbk.get(k) != "N/A":
                    metrics[k] = metrics_gbk[k]

        # 若关键指标全为 N/A，把原始输出的汇总部分存到调试文件供正则调试
        if metrics.get("sharpe") == "N/A" and metrics.get("total_profit_pct") == "N/A":
            debug_path = OUTPUT_DIR / f"_debug_{phase_key}.txt"
            # 只保留含指标的关键行（减小文件体积）
            key_lines = [ln for ln in output.splitlines()
                         if any(k in ln for k in (
                             "Sharpe", "Sortino", "SQN", "Calmar", "CAGR",
                             "Profit", "Underwater", "drawdown", "Market Change",
                             "balance", "TOTAL", "roi", "stop_loss", "momentum",
                             "Long", "总收益率", "│", "|",
                         ))]
            debug_path.write_text("\n".join(key_lines[-200:]), encoding="utf-8")
            print(f"  ⚠ 指标提取失败，调试输出已保存: {debug_path}")

        print(f"  ✓ 完成 | 利润: {metrics.get('total_profit_pct','N/A')}%  "
              f"Sharpe: {metrics.get('sharpe','N/A')}  "
              f"Sortino: {metrics.get('sortino','N/A')}  "
              f"Calmar: {metrics.get('calmar','N/A')}  "
              f"回撤: {metrics.get('max_drawdown_pct','N/A')}%")

        return {
            "phase":       phase_key,
            "phase_label": phase["label"],
            "phase_desc":  phase["description"],
            "market":      phase["market"],
            "btc_change":  _live_btc or phase["btc_change"],
            "btc_source":  btc_src,
            "timerange":   phase["range"],
            "status":      "OK",
            **metrics,
            "exits":       exits,
            "raw_tail":    output[-3000:],
        }

    except subprocess.TimeoutExpired:
        print(f"  ✗ 超时 (>900s)")
        return {"phase": phase_key, "phase_label": phase["label"], "status": "TIMEOUT"}
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return {"phase": phase_key, "phase_label": phase["label"], "status": "ERROR", "error": str(e)}


# ─── 阶段评估引擎 ─────────────────────────────────────────────────────────────
def evaluate_phase(r):
    strengths = []
    weaknesses = []

    def flt(key, default=0.0):
        try:
            return float(r.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    sharpe   = flt("sharpe")
    sortino  = flt("sortino")
    calmar   = flt("calmar")
    profit   = flt("total_profit_pct")
    drawdown = flt("max_drawdown_pct")
    win_rate = flt("win_rate")
    pf       = flt("profit_factor")
    sqn      = flt("sqn")
    long_p   = flt("long_profit_pct", -999)
    short_p  = flt("short_profit_pct", -999)

    exits   = r.get("exits", {})
    def _int_safe(v, default=0):
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return default

    roi_cnt = _int_safe(exits.get("roi",       {}).get("count", 0))
    sl_cnt  = _int_safe(exits.get("stop_loss", {}).get("count", 0))
    ml_cnt  = _int_safe(exits.get("mtm_long",  {}).get("count", 0))
    ms_cnt  = _int_safe(exits.get("mtm_short", {}).get("count", 0))
    total_t = _int_safe(r.get("trades", 1), default=1) or 1
    momentum_exit_pct = (ml_cnt + ms_cnt) / max(total_t, 1) * 100

    # 盈利能力
    if profit > 50:
        strengths.append(f"高收益: 总利润 {profit:.1f}%，表现强劲")
    elif profit > 10:
        strengths.append(f"正收益: 总利润 {profit:.1f}%")
    elif profit > 0:
        weaknesses.append(f"收益微薄: 总利润仅 {profit:.1f}%，安全边际不足")
    else:
        weaknesses.append(f"亏损: 总利润 {profit:.1f}%")

    # 风险调整收益
    if sharpe > 3:
        strengths.append(f"优秀风险收益比: Sharpe {sharpe:.2f} / Sortino {sortino:.2f}")
    elif sharpe > 1:
        strengths.append(f"良好风险收益比: Sharpe {sharpe:.2f}")
    elif sharpe > 0:
        weaknesses.append(f"风险收益比偏低: Sharpe {sharpe:.2f}，收益与波动不匹配")
    else:
        weaknesses.append(f"风险收益比为负: Sharpe {sharpe:.2f}，系统性亏损")

    # 回撤控制
    if drawdown < 10:
        strengths.append(f"回撤极佳: 最大回撤仅 {drawdown:.1f}%，风控有效")
    elif drawdown < 20:
        strengths.append(f"回撤可接受: 最大回撤 {drawdown:.1f}%")
    elif drawdown < 30:
        weaknesses.append(f"回撤偏高: 最大回撤 {drawdown:.1f}%，心理压力较大")
    else:
        weaknesses.append(f"回撤严重: 最大回撤 {drawdown:.1f}%，实盘难以承受")

    # Calmar
    if calmar > 10:
        strengths.append(f"Calmar 出色: {calmar:.2f}，单位回撤创造高回报")
    elif 0 < calmar < 2 and profit > 0:
        weaknesses.append(f"Calmar 偏低: {calmar:.2f}，需承担较大回撤换取盈利")

    # SQN
    if sqn > 3:
        strengths.append(f"系统质量高: SQN {sqn:.2f} (>3为优秀)")
    elif sqn > 1.6:
        strengths.append(f"系统质量良好: SQN {sqn:.2f}")
    elif sqn < 1:
        weaknesses.append(f"系统质量差: SQN {sqn:.2f} (<1为边缘水平)")

    # 出场结构
    if roi_cnt > 0 and total_t > 0:
        roi_ratio = roi_cnt / total_t * 100
        if roi_ratio > 50:
            strengths.append(f"ROI出场占比高: {roi_ratio:.0f}%，策略能有效锁定利润")
        elif roi_ratio < 30:
            weaknesses.append(f"ROI出场占比低: 仅 {roi_ratio:.0f}%，大量交易未能到达目标收益")

    if momentum_exit_pct > 40:
        weaknesses.append(
            f"Momentum Exit 过度激进: 占全部出场 {momentum_exit_pct:.0f}%"
            f" (long:{ml_cnt}次 short:{ms_cnt}次)，提前割肉损耗严重"
        )
    elif momentum_exit_pct < 20 and total_t > 50:
        strengths.append(f"Momentum Exit 触发率低: {momentum_exit_pct:.0f}%，信号质量良好")

    if sl_cnt > 0:
        sl_ratio = sl_cnt / total_t * 100
        if sl_ratio > 3:
            weaknesses.append(f"止损触发频繁: {sl_cnt}次({sl_ratio:.1f}%)，趋势判断存在问题")
        else:
            strengths.append(f"止损控制良好: 仅 {sl_cnt}次({sl_ratio:.1f}%)，硬止损未被频繁触发")

    # 多空方向
    if long_p > 0 and short_p > 0:
        strengths.append(f"多空双向盈利: 多头 +{long_p:.1f}%，空头 +{short_p:.1f}%")
    elif long_p != -999 and short_p != -999:
        if long_p < 0 and short_p > 5:
            weaknesses.append(f"多头失效: 多头 {long_p:.1f}%，依赖空头盈利；当前市场做多不利")
        elif long_p > 5 and short_p < 0:
            weaknesses.append(f"空头失效: 空头 {short_p:.1f}%；当前市场做空不利")

    # 获利因子
    if pf < 1.05 and total_t > 50:
        weaknesses.append(f"获利因子过低: {pf:.2f}，几乎无安全边际，滑点即可致亏")
    elif pf > 1.3:
        strengths.append(f"获利因子健康: {pf:.2f}")

    # 综合评分
    score = 0
    if sharpe > 3:    score += 3
    elif sharpe > 1:  score += 2
    elif sharpe > 0:  score += 1
    if drawdown < 15: score += 2
    elif drawdown < 25: score += 1
    if profit > 30:   score += 2
    elif profit > 5:  score += 1
    if calmar > 5:    score += 1
    if pf > 1.2:      score += 1

    if score >= 7:    rating = "★★★★★ 优秀"
    elif score >= 5:  rating = "★★★★  良好"
    elif score >= 3:  rating = "★★★   一般"
    elif score >= 1:  rating = "★★    较差"
    else:             rating = "★     很差"

    return {"rating": rating, "score": score, "strengths": strengths, "weaknesses": weaknesses}


# ─── 终端报告打印器 ───────────────────────────────────────────────────────────
def print_terminal_report(strategy, results):
    W = 92
    print("\n" + "=" * W)
    print(f"  策略十四阶段周期分析报告 — {strategy}")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * W)

    ok_results = [r for r in results if r.get("status") == "OK"]

    # 汇总表
    print(f"\n  {'阶段':<14} {'市场':<10} {'利润%':>8} {'Sharpe':>8} {'Sortino':>8} "
          f"{'Calmar':>8} {'回撤%':>7} {'SQN':>6} {'胜率%':>7} {'PF':>6}  {'评级'}")
    print("  " + "-" * (W - 2))

    for r in results:
        if r.get("status") != "OK":
            label = r.get("phase_label", r.get("phase", "?"))
            print(f"  {label:<14} {'--':<10} {'FAILED':>8}")
            continue
        ev = evaluate_phase(r)
        print(
            f"  {r.get('phase_label',''):<14} {r.get('market',''):<10}"
            f" {r.get('total_profit_pct','N/A'):>8}"
            f" {r.get('sharpe','N/A'):>8}"
            f" {r.get('sortino','N/A'):>8}"
            f" {r.get('calmar','N/A'):>8}"
            f" {r.get('max_drawdown_pct','N/A'):>7}"
            f" {r.get('sqn','N/A'):>6}"
            f" {r.get('win_rate','N/A'):>7}"
            f" {r.get('profit_factor','N/A'):>6}  {ev['rating']}"
        )

    # 每阶段详细评估
    print("\n" + "=" * W)
    print("  各阶段详细评估")
    print("=" * W)

    for r in results:
        if r.get("status") != "OK":
            continue
        ev    = evaluate_phase(r)
        exits = r.get("exits", {})

        print(f"\n  {r['phase_label']}  [{r.get('timerange','')}]")
        print(f"  {r.get('phase_desc','')}  |  市场: {r.get('market','')} (BTC {r.get('btc_change','')})")
        print(f"  综合评级: {ev['rating']}")
        print()
        print(f"    核心指标: 利润 {r.get('total_profit_pct','N/A')}%  "
              f"CAGR {r.get('cagr_pct','N/A')}%  "
              f"Sharpe {r.get('sharpe','N/A')}  "
              f"Sortino {r.get('sortino','N/A')}  "
              f"Calmar {r.get('calmar','N/A')}  "
              f"回撤 {r.get('max_drawdown_pct','N/A')}%  "
              f"SQN {r.get('sqn','N/A')}")
        print(f"    多空收益: 多头 {r.get('long_profit_pct','N/A')}%  "
              f"空头 {r.get('short_profit_pct','N/A')}%  "
              f"交易次数 {r.get('trades','N/A')}  "
              f"胜率 {r.get('win_rate','N/A')}%  "
              f"获利因子 {r.get('profit_factor','N/A')}")

        exit_parts = []
        for name, lbl in [("roi","ROI"), ("stop_loss","StopLoss"),
                          ("mtm_long","MtmExitLong"), ("mtm_short","MtmExitShort")]:
            e = exits.get(name)
            if e:
                exit_parts.append(f"{lbl}:{e['count']}次({e['avg_pct']}%均)")
        if exit_parts:
            print(f"    出场分解: {' | '.join(exit_parts)}")

        if ev["strengths"]:
            print()
            print("    [优势]")
            for s in ev["strengths"]:
                print(f"      + {s}")
        if ev["weaknesses"]:
            print()
            print("    [劣势/风险]")
            for w in ev["weaknesses"]:
                print(f"      - {w}")
        print("  " + "-" * (W - 4))

    # 跨周期综合结论
    if ok_results:
        print("\n" + "=" * W)
        print("  跨周期综合结论")
        print("=" * W)

        evals      = [(r, evaluate_phase(r)) for r in ok_results]
        best       = max(evals, key=lambda x: x[1]["score"])
        worst      = min(evals, key=lambda x: x[1]["score"])
        sharpes    = [_flt_safe(r.get("sharpe", 0), 0.0) for r in ok_results]
        avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0
        dds        = [_flt_safe(r.get("max_drawdown_pct", 0), 0.0) for r in ok_results]
        avg_dd     = sum(dds) / len(dds) if dds else 0
        profits    = [_flt_safe(r.get("total_profit_pct", 0), 0.0) for r in ok_results]
        positive   = sum(1 for p in profits if p > 0)

        print(f"\n  最强阶段: {best[0]['phase_label']}  ({best[1]['rating']})  Sharpe {best[0].get('sharpe','N/A')}")
        print(f"  最弱阶段: {worst[0]['phase_label']}  ({worst[1]['rating']})  Sharpe {worst[0].get('sharpe','N/A')}")
        print(f"  平均 Sharpe: {avg_sharpe:.2f}  |  平均最大回撤: {avg_dd:.1f}%")
        print(f"  盈利阶段: {positive}/{len(ok_results)} 个周期为正收益")
        print()

        if avg_sharpe > 2 and positive == len(ok_results):
            print("  [✓] 策略跨周期稳定性优秀，全部阶段盈利，风险收益比持续为正")
        elif avg_sharpe > 1 and positive >= len(ok_results) * 0.8:
            print("  [✓] 策略具备较好的跨周期适应性，大多数阶段表现良好")
        elif positive >= len(ok_results) * 0.5:
            print("  [!] 策略在特定市场环境有效，但跨周期一致性有待改善")
        else:
            print("  [✗] 策略跨周期稳定性较差，多个阶段出现亏损，存在结构性风险")

    print("\n" + "=" * W + "\n")


# ─── HTML 报告生成器 ──────────────────────────────────────────────────────────
def generate_html_report(strategy, results, out_path):

    def _val(r, key, suffix=""):
        v = r.get(key, "N/A")
        if v == "N/A" or v is None:
            return '<span class="na">N/A</span>'
        try:
            f = float(v)
            cls = ""
            if key in ("total_profit_pct", "long_profit_pct", "short_profit_pct", "cagr_pct"):
                cls = "pos" if f > 0 else "neg"
            elif key == "sharpe":
                cls = "pos" if f > 1 else ("warn" if f > 0 else "neg")
            elif key == "max_drawdown_pct":
                cls = "pos" if f < 15 else ("warn" if f < 25 else "neg")
            return f'<span class="{cls}">{v}{suffix}</span>'
        except (TypeError, ValueError):
            return f"<span>{v}{suffix}</span>"

    phase_order = [
        "bull_2021q1", "crash_china", "bull_2021ath",
        "bear_orderly", "luna_crisis", "ftx_bottom",
        "recovery", "etf_halving", "election_bull",
        "correction_2025", "tariff_shock", "btc_ath_2025",
        "btc_crash_2026", "btc_recovery_2026",
    ]
    ordered = {r["phase"]: r for r in results if "phase" in r}

    rows_html  = ""
    cards_html = ""

    for pk in phase_order:
        r = ordered.get(pk)
        if not r:
            continue

        if r.get("status") != "OK":
            rows_html += f"""
            <tr>
              <td><b>{r.get('phase_label','?')}</b></td>
              <td colspan="10" style="color:#999">回测失败 ({r.get('status','')})</td>
            </tr>"""
            continue

        ev    = evaluate_phase(r)
        exits = r.get("exits", {})
        stars = ev["rating"].split()[0]

        rows_html += f"""
        <tr>
          <td><b>{r['phase_label']}</b><br><small>{r.get('market','')} BTC{r.get('btc_change','')}</small></td>
          <td>{_val(r,'total_profit_pct','%')}</td>
          <td>{_val(r,'cagr_pct','%')}</td>
          <td>{_val(r,'sharpe')}</td>
          <td>{_val(r,'sortino')}</td>
          <td>{_val(r,'calmar')}</td>
          <td>{_val(r,'sqn')}</td>
          <td>{_val(r,'max_drawdown_pct','%')}</td>
          <td>{_val(r,'profit_factor')}</td>
          <td>{_val(r,'win_rate','%')}</td>
          <td>{stars}</td>
        </tr>"""

        exit_rows = ""
        for name, lbl, color in [
            ("roi",       "ROI止盈",    "#2ecc71"),
            ("stop_loss", "硬止损",     "#e74c3c"),
            ("mtm_long",  "动量退出多", "#e67e22"),
            ("mtm_short", "动量退出空", "#e67e22"),
        ]:
            e = exits.get(name)
            if e:
                exit_rows += f"""
                <tr>
                  <td style="color:{color};font-weight:bold">{lbl}</td>
                  <td>{e.get('count','?')} 次</td>
                  <td>{e.get('avg_pct','?')}% (均)</td>
                  <td>{e.get('total_pct','?')}% (总)</td>
                </tr>"""

        s_html = "".join(f'<li class="strength">{s}</li>' for s in ev["strengths"])
        w_html = "".join(f'<li class="weakness">{w}</li>' for w in ev["weaknesses"])

        lp_val  = r.get('long_profit_pct', 'N/A')
        sp_val  = r.get('short_profit_pct', 'N/A')
        lp_cls  = "pos" if _is_pos(lp_val) else "neg"
        sp_cls  = "pos" if _is_pos(sp_val) else "neg"
        prf_cls = "pos" if _is_pos(r.get('total_profit_pct')) else "neg"
        dd_val  = r.get('max_drawdown_pct', '99')
        dd_cls  = "pos" if _flt_safe(dd_val) < 15 else ("warn" if _flt_safe(dd_val) < 25 else "neg")

        cards_html += f"""
        <div class="card">
          <div class="card-header">
            <span class="phase-label">{r['phase_label']}</span>
            <span class="timerange">[{r.get('timerange','')}]</span>
            <span class="rating">{ev['rating']}</span>
          </div>
          <p class="desc">{r.get('phase_desc','')} &nbsp;|&nbsp; 市场: <b>{r.get('market','')}</b> (BTC {r.get('btc_change','')})</p>
          <div class="metrics-grid">
            <div class="metric"><div class="m-label">总利润</div><div class="m-val {prf_cls}">{r.get('total_profit_pct','N/A')}%</div></div>
            <div class="metric"><div class="m-label">CAGR</div><div class="m-val">{r.get('cagr_pct','N/A')}%</div></div>
            <div class="metric"><div class="m-label">Sharpe</div><div class="m-val">{r.get('sharpe','N/A')}</div></div>
            <div class="metric"><div class="m-label">Sortino</div><div class="m-val">{r.get('sortino','N/A')}</div></div>
            <div class="metric"><div class="m-label">Calmar</div><div class="m-val">{r.get('calmar','N/A')}</div></div>
            <div class="metric"><div class="m-label">SQN</div><div class="m-val">{r.get('sqn','N/A')}</div></div>
            <div class="metric"><div class="m-label">最大回撤</div><div class="m-val {dd_cls}">{r.get('max_drawdown_pct','N/A')}%</div></div>
            <div class="metric"><div class="m-label">获利因子</div><div class="m-val">{r.get('profit_factor','N/A')}</div></div>
            <div class="metric"><div class="m-label">胜率</div><div class="m-val">{r.get('win_rate','N/A')}%</div></div>
            <div class="metric"><div class="m-label">多头利润</div><div class="m-val {lp_cls}">{lp_val}%</div></div>
            <div class="metric"><div class="m-label">空头利润</div><div class="m-val {sp_cls}">{sp_val}%</div></div>
            <div class="metric"><div class="m-label">交易次数</div><div class="m-val">{r.get('trades','N/A')}</div></div>
          </div>
          {"<table class='exit-table'><tr><th>出场原因</th><th>次数</th><th>平均收益</th><th>总收益%</th></tr>" + exit_rows + "</table>" if exit_rows else ""}
          <div class="eval-section">
            {"<div class='eval-group'><div class='eval-title'>✅ 优势</div><ul>" + s_html + "</ul></div>" if s_html else ""}
            {"<div class='eval-group'><div class='eval-title'>⚠ 劣势/风险</div><ul>" + w_html + "</ul></div>" if w_html else ""}
          </div>
        </div>"""

    # ── 图表数据构建（策略链式净值 + BTC链式净值 + 每阶段利润%）──────────────
    _clab, _ceq, _cbtc, _csh, _cpr, _cdd, _cco, _cbtc_pct, _ctr = [], [1000.0], [1000.0], [], [], [], [], [], []
    _rn  = 1000.0
    _rbt = 1000.0
    for _pk in phase_order:
        _rx = ordered.get(_pk)
        if not _rx or _rx.get("status") != "OK":
            continue
        _px  = _flt_safe(_rx.get("total_profit_pct", 0), 0.0)
        _sx  = _flt_safe(_rx.get("sharpe",            0), 0.0)
        _dx  = _flt_safe(_rx.get("max_drawdown_pct",  0), 0.0)
        _btc_str = str(_rx.get("btc_change", "0")).replace("%", "").replace("+", "")
        try:
            _bx = float(_btc_str)
        except ValueError:
            _bx = 0.0
        _rn  *= (1 + _px  / 100)
        _rbt *= (1 + _bx  / 100)
        _clab.append(_rx.get("phase_label", _pk))
        _ceq.append(round(_rn,  1))
        _cbtc.append(round(_rbt, 1))
        _csh.append(round(_sx,  2))
        _cpr.append(round(_px,  2))
        _cdd.append(round(_dx,  1))
        _cco.append("rgba(74,222,128,0.8)" if _px >= 0 else "rgba(248,113,113,0.8)")
        _cbtc_pct.append(round(_bx, 1))
        _ctr.append(_rx.get("timerange", ""))
    _maxdd_i = _cdd.index(max(_cdd)) if _cdd else 0
    _cjson = json.dumps(
        {"labels": _clab,
         "equity": _ceq, "btc": _cbtc,
         "profit": _cpr, "btc_pct": _cbtc_pct,
         "sharpe": _csh, "drawdown": _cdd, "barColors": _cco,
         "timeranges": _ctr, "maxDdIdx": _maxdd_i},
        ensure_ascii=False,
    )
    _full_cjs = "const D=" + _cjson + ";" + _CHART_JS_TEMPLATE
    _n_phases  = len(_clab)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{strategy} — {_n_phases}阶段周期分析报告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;background:#12151e;color:#dde4f0;font-size:14px;line-height:1.5}}
.header{{background:linear-gradient(135deg,#1c2235 0%,#1e2a45 100%);padding:32px 40px;border-bottom:2px solid #3a4870}}
.header h1{{font-size:26px;color:#eaf0ff;margin-bottom:8px;font-weight:700}}
.header p{{color:#96a8cc;font-size:13px}}
.container{{max-width:1400px;margin:0 auto;padding:32px 24px}}
h2{{color:#c8d8ff;font-size:15px;font-weight:700;margin:36px 0 14px;padding-left:12px;border-left:4px solid #4f7ef5;letter-spacing:.04em}}
.summary-table{{width:100%;border-collapse:collapse;margin-bottom:36px;background:#1c2235;border-radius:10px;overflow:hidden;border:1px solid #2e3a5a}}
.summary-table th{{background:#243050;color:#a0b4d8;font-weight:700;padding:12px 14px;text-align:right;font-size:12px;letter-spacing:.05em;border-bottom:2px solid #3a4870}}
.summary-table th:first-child{{text-align:left}}
.summary-table td{{padding:11px 14px;text-align:right;border-top:1px solid #283048;color:#dde4f0;font-size:13px}}
.summary-table td:first-child{{text-align:left}}
.summary-table td small{{color:#7a90b8;font-size:11px;display:block;margin-top:2px}}
.summary-table tr:hover td{{background:#22304a}}
.pos{{color:#4ade80;font-weight:700}}
.neg{{color:#f87171;font-weight:700}}
.warn{{color:#fbbf24;font-weight:700}}
.na{{color:#5a6880;font-style:italic}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(620px,1fr));gap:22px}}
.card{{background:#1c2235;border:1px solid #2e3a5a;border-radius:12px;padding:22px 26px}}
.card-header{{display:flex;align-items:baseline;gap:10px;margin-bottom:8px;flex-wrap:wrap}}
.phase-label{{font-size:18px;font-weight:800;color:#eaf0ff}}
.timerange{{font-size:12px;color:#7a90b8;background:#243050;padding:2px 8px;border-radius:4px}}
.rating{{font-size:14px;margin-left:auto;font-weight:600;color:#fbbf24}}
.desc{{color:#96a8cc;font-size:12px;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #283048}}
.desc b{{color:#c8d8ff}}
.metrics-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:18px}}
.metric{{background:#243050;border:1px solid #2e3a5a;border-radius:8px;padding:10px 8px;text-align:center}}
.m-label{{font-size:10px;color:#7a90b8;margin-bottom:4px;font-weight:600;letter-spacing:.06em;text-transform:uppercase}}
.m-val{{font-size:16px;font-weight:800;color:#dde4f0}}
.exit-table{{width:100%;border-collapse:collapse;margin-bottom:16px;font-size:12px;background:#1a2030;border-radius:6px;overflow:hidden}}
.exit-table th{{color:#96a8cc;text-align:left;padding:7px 10px;background:#243050;font-weight:600;border-bottom:1px solid #2e3a5a}}
.exit-table td{{padding:6px 10px;border-bottom:1px solid #232d45;color:#c8d8ff}}
.eval-section{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}}
.eval-group{{background:#172030;border:1px solid #2e3a5a;border-radius:8px;padding:12px 16px}}
.eval-title{{font-size:12px;font-weight:700;margin-bottom:8px;color:#a0b4d8;letter-spacing:.05em}}
.eval-group ul{{padding-left:16px}}
li.strength{{color:#4ade80;font-size:12px;margin-bottom:4px;line-height:1.5}}
li.weakness{{color:#f87171;font-size:12px;margin-bottom:4px;line-height:1.5}}
.footer{{text-align:center;color:#5a6880;font-size:12px;padding:36px;border-top:1px solid #283048;margin-top:20px}}
.chart-wrap{{background:#1c2235;border:1px solid #2e3a5a;border-radius:12px;padding:22px 26px;margin-bottom:18px}}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
</head>
<body>
<div class="header">
  <h1>&#128202; {strategy} — {_n_phases}阶段市场周期分析报告</h1>
  <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
     覆盖周期: 2021-01 → 2026-04 &nbsp;|&nbsp; 14个市场结构阶段</p>
</div>
<div class="container">
  <h2>策略净值曲线 vs BTC基准</h2>
  <div class="chart-wrap"><canvas id="equityChart" height="140"></canvas></div>
  <h2>汇总对比</h2>
  <table class="summary-table">
    <thead>
      <tr>
        <th>阶段</th><th>利润%</th><th>CAGR%</th><th>Sharpe</th>
        <th>Sortino</th><th>Calmar</th><th>SQN</th>
        <th>最大回撤%</th><th>获利因子</th><th>胜率%</th><th>评级</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <h2>各阶段详细分析</h2>
  <div class="cards">{cards_html}</div>
</div>
<div class="footer">由 batch_compare.py 自动生成 &nbsp;|&nbsp; MomentumFusion 策略审计工具</div>
<script>__CJS__</script>
</body>
</html>"""
    html = html.replace("__CJS__", _full_cjs)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  ✓ HTML 报告已生成: {out_path}")


# ─── 图表 JS 模板（普通字符串，非 f-string，避免花括号转义）────────────────────
_CHART_JS_TEMPLATE = """
Chart.defaults.color = '#96a8cc';

// ── 数据准备 ──────────────────────────────────────────────────────────────────
const _allL = ['起始(1000U)', ...D.labels];
// 回撤：起始点 0，其余取负（向下展示）
const _ddV  = [0, ...D.drawdown.map(v => -v)];
// 找最大回撤所在阶段（D.labels 的 0-based 索引）
const _maxDdI = D.drawdown.indexOf(Math.max(...D.drawdown));
// 格式化时间段 "20210101-20210430" → "2021.01—2021.04"
function _fmtTR(s){
  if(!s||s.length<15)return s||'';
  return s.slice(0,4)+'.'+s.slice(4,6)+'—'+s.slice(9,13)+'.'+s.slice(13,15);
}

// ── 注解：阶段分隔线 + 最大回撤高亮框 + 阶段时间段标签 ──────────────────────
const _ann = {};
for(let i = 0; i < D.labels.length; i++){
  // 每个阶段之间的竖向虚线（从索引 0.5 开始，每阶段间隔一格）
  if(i > 0){
    _ann['vl'+i] = {
      type: 'line', scaleID: 'x', value: i + 0.5,
      borderColor: 'rgba(200,216,255,0.10)', borderWidth: 1, borderDash: [4,4]
    };
  }
}
// 最大回撤阶段：红色高亮框
_ann.maxDdBox = {
  type: 'box',
  xMin: _maxDdI + 0.5, xMax: _maxDdI + 1.5,
  yScaleID: 'yEq',
  backgroundColor: 'rgba(248,113,113,0.09)',
  borderColor:     'rgba(248,113,113,0.55)',
  borderWidth: 1.5,
  label: {
    display: true,
    content: ['▼ 最大回撤区间', D.labels[_maxDdI], D.drawdown[_maxDdI]+'%'],
    color: '#f87171', font: {size: 10, weight: 'bold'},
    position: {x: 'center', y: 'start'}, yAdjust: 8
  }
};

// ── 图表渲染 ──────────────────────────────────────────────────────────────────
new Chart(document.getElementById('equityChart'), {
  data: {
    labels: _allL,
    datasets: [
      // ① 回撤深度（右轴，向下填充至 0）—— 先渲染，压在底层
      {
        type: 'line', label: '阶段最大回撤（右轴↓）',
        data: _ddV,
        borderColor: 'rgba(248,113,113,0.5)',
        backgroundColor: 'rgba(248,113,113,0.15)',
        borderWidth: 1.5,
        pointRadius: _allL.map((_,i) => i===0 ? 0 : 4),
        pointBackgroundColor: 'rgba(248,113,113,0.8)',
        fill: 'origin', tension: 0.1,
        yAxisID: 'yDd', order: 10
      },
      // ② BTC 持有基准（左轴）
      {
        type: 'line', label: 'BTC 持有基准（归一至 1000U）',
        data: D.btc,
        borderColor: '#f59e0b',
        backgroundColor: 'transparent',
        borderWidth: 2, borderDash: [6, 4],
        pointRadius: _allL.map((_,i) => i===0 ? 3 : 5),
        pointBackgroundColor: ['#7a90b8', ...D.btc.slice(1).map((v,i)=>D.btc[i]<v?'#fbbf24':'#f87171')],
        fill: false, tension: 0.3,
        yAxisID: 'yEq', order: 2
      },
      // ③ 策略净值（左轴）——最上层
      {
        type: 'line', label: '策略净值（USDT）',
        data: D.equity,
        borderColor: '#4f7ef5',
        backgroundColor: 'rgba(79,126,245,0.07)',
        borderWidth: 2.5,
        pointRadius: _allL.map((_,i) => i===0 ? 4 : 6),
        pointBackgroundColor: ['#96a8cc', ...D.barColors],
        fill: true, tension: 0.3,
        yAxisID: 'yEq', order: 1
      }
    ]
  },
  options: {
    responsive: true,
    interaction: {mode: 'index', intersect: false},
    plugins: {
      legend: {
        labels: {
          color: '#dde4f0', font: {size: 12},
          boxWidth: 24, padding: 18,
          // 把回撤图例放最后（视觉上已区分）
        }
      },
      title: {
        display: true, color: '#c8d8ff', font: {size: 14, weight: 'bold'},
        text: '策略净值曲线 vs BTC持有基准  |  红色区域 = 各阶段最大回撤',
        padding: {bottom: 18}
      },
      annotation: {annotations: _ann},
      tooltip: {
        backgroundColor: '#1c2235', borderColor: '#3a4870', borderWidth: 1,
        padding: 12, titleFont: {size: 13, weight: 'bold'},
        callbacks: {
          title: (items) => {
            const i = items[0].dataIndex;
            if(i === 0) return '起始点';
            const k = i - 1;
            return D.labels[k] + '  [' + _fmtTR(D.timeranges[k]) + ']';
          },
          label: (item) => {
            const i = item.dataIndex;
            if(i === 0){
              if(item.datasetIndex === 2) return ' 初始资金: 1,000 USDT';
              return null;
            }
            const k = i - 1;
            if(item.datasetIndex === 2){
              const gain = D.profit[k];
              return ' 策略净值: ' + D.equity[i] + ' U  (' + (gain>=0?'+':'') + gain + '%)';
            }
            if(item.datasetIndex === 1){
              const bg = D.btc_pct[k];
              return ' BTC基准:  ' + D.btc[i] + ' U  (' + (bg>=0?'+':'') + bg + '%)';
            }
            if(item.datasetIndex === 0){
              return ' 本阶段最大回撤: ' + D.drawdown[k] + '%';
            }
            return null;
          },
          afterBody: (items) => {
            const i = items[0].dataIndex - 1;
            if(i < 0) return [];
            const diff = (D.profit[i] - D.btc_pct[i]).toFixed(1);
            const beat = parseFloat(diff) >= 0
              ? '✓ 跑赢 BTC  超额 +' + diff + '%'
              : '✗ 跑输 BTC  差距 ' + diff + '%';
            const sh = D.sharpe[i];
            const sq = sh >= 2 ? '★★★优秀' : sh >= 1 ? '★★良好' : sh >= 0 ? '★一般' : '✗亏损';
            return [
              '',
              ' Sharpe: ' + sh + '  →  ' + sq,
              ' ' + beat
            ];
          }
        }
      }
    },
    scales: {
      x: {
        ticks: {color: '#96a8cc', maxRotation: 20, font: {size: 10}},
        grid:  {color: '#1a2333'}
      },
      yEq: {
        position: 'left',
        ticks: {
          color: '#96a8cc',
          callback: v => v >= 10000 ? (v/1000).toFixed(0)+'K' : v >= 1000 ? (v/1000).toFixed(1)+'K' : v
        },
        grid: {color: '#1e2a3a'},
        title: {display: true, text: '净值 (USDT)', color: '#7a90b8', font: {size: 11}}
      },
      yDd: {
        position: 'right',
        max: 0,
        ticks: {
          color: '#f87171',
          callback: v => (-v).toFixed(0) + '%'
        },
        grid: {drawOnChartArea: false},
        title: {display: true, text: '最大回撤% (↓越深越险)', color: '#f87171', font: {size: 11}},
        afterDataLimits(axis){ axis.min = Math.min(axis.min, -40); }
      }
    }
  }
});
"""


def _is_pos(v):
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def _flt_safe(v, default=99.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ─── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="单策略十四阶段周期回测分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整十四阶段分析
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5

  # 只跑特定阶段
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5 --phases bull_2021q1 luna_crisis etf_halving tariff_shock btc_ath_2025 btc_crash_2026

  # 预览命令（不执行）
  conda activate freqAi ; python scripts/batch_compare.py --config user_data/config_mf_v2.json --strategy MomentumFusion_V5 --dry-run

  # 从已有 JSON 结果重新生成报告
  conda activate freqAi ; python scripts/batch_compare.py --from-json user_data/bt_extracted/phase_analysis_xxx.json
"""
    )
    parser.add_argument("--config",    help="freqtrade config 文件路径")
    parser.add_argument("--strategy",  help="策略名称（.py 文件名，不含后缀）")
    parser.add_argument(
        "--phases", nargs="+",
        choices=list(PHASES.keys()),
        default=list(PHASES.keys()),
        help=f"指定阶段 (默认全部): {list(PHASES.keys())}",
    )
    parser.add_argument("--dry-run",   action="store_true", help="仅打印命令，不执行")
    parser.add_argument("--from-json", metavar="FILE",      help="跳过回测，从已有 JSON 生成报告")
    parser.add_argument("--no-html",   action="store_true", help="不生成 HTML 报告")
    args = parser.parse_args()

    # 从已有 JSON 生成报告
    if args.from_json:
        json_path = Path(args.from_json)
        if not json_path.exists():
            print(f"错误: 文件不存在 {json_path}")
            return 1
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        strategy_name = data.get("strategy", "Unknown")
        results       = data.get("results", [])

        # 尝试用本地 K 线更新 btc_change 为精确值
        _btc_df = _load_btc_df(args.config)
        if _btc_df is not None:
            _enriched = 0
            for _r in results:
                _rng = _r.get("timerange") or PHASES.get(_r.get("phase", ""), {}).get("range")
                if _rng:
                    _real = _btc_pct_from_range(_btc_df, _rng)
                    if _real:
                        _r["btc_change"] = _real
                        _r["btc_source"] = "实时"
                        _enriched += 1
            if _enriched:
                print(f"  ✓ 已用本地 K 线更新 {_enriched} 个阶段的 BTC 精确涨跌幅")
        else:
            print("  ⚠ 未找到本地 BTC K 线，btc_change 使用 JSON 中已有值（可能为估算）")

        print_terminal_report(strategy_name, results)
        if not args.no_html:
            html_path = json_path.with_suffix(".html")
            generate_html_report(strategy_name, results, html_path)
        return 0

    # 正常流程
    if not args.config or not args.strategy:
        parser.print_help()
        print("\n错误: 必须同时指定 --config 和 --strategy\n")
        return 1

    strategy = args.strategy
    phases   = args.phases
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"phase_analysis_{strategy}_{ts}.json"
    html_path = OUTPUT_DIR / f"phase_analysis_{strategy}_{ts}.html"

    print(f"\n{'#'*72}")
    print(f"  策略十四阶段周期分析启动")
    print(f"  Config  : {args.config}")
    print(f"  Strategy: {strategy}")
    print(f"  阶段    : {phases}  ({len(phases)} 个)")
    print(f"  预计耗时: ~{len(phases) * 3} 分钟")
    print(f"{'#'*72}")

    if args.dry_run:
        for pk in phases:
            ph = PHASES[pk]
            print(f"  [DRY]  freqtrade backtesting --config {args.config} "
                  f"--strategy {strategy} --timerange {ph['range']}")
            print(f"         {ph['label']}  {ph['description']}")
        return 0

    # ── 检查 BTC 本地 K 线覆盖情况 ──────────────────────────────────────────────
    print("\n  [BTC数据检查] 正在读取本地 K 线...")
    btc_df, btc_missing = check_btc_data(args.config, phases)
    if btc_df is not None:
        print(f"  ✓ BTC K线已加载 ({len(btc_df)} 根 1h 蜡烛，"
              f"{btc_df['date'].min().strftime('%Y-%m-%d')} ~ "
              f"{btc_df['date'].max().strftime('%Y-%m-%d')})")
    if btc_missing:
        print(f"\n  ⚠ 以下阶段的 BTC K线数据不完整，精确 BTC 涨跌幅将降级为内置估算值：")
        for m in btc_missing:
            print(f"    [{m['phase']}]  {m['reason']}")
        print(f"\n  ℹ 建议先下载完整数据：")
        print(f"    conda activate freqAi ; freqtrade download-data "
              f"--config {args.config} --pairs BTC/USDT:USDT --timeframes 1h --timerange 20210101-\n")

    results = []
    for i, pk in enumerate(phases, 1):
        print(f"\n[{i}/{len(phases)}]", end="")
        record = run_backtest(args.config, strategy, pk, btc_df=btc_df)
        results.append(record)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"strategy": strategy, "config": args.config,
                 "generated": ts, "results": results},
                f, ensure_ascii=False, indent=2,
            )

    print_terminal_report(strategy, results)

    if not args.no_html:
        generate_html_report(strategy, results, html_path)

    print(f"  JSON 数据: {json_path}")
    if not args.no_html:
        print(f"  HTML 报告: {html_path}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
