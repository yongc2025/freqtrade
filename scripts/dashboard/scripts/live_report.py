"""
live_report.py — 实盘数据库 → 回测格式报告生成器
将 Freqtrade SQLite 实盘数据库转换为与 freqtrade backtesting 输出完全一致的格式。
用法: python live_report.py [数据库路径] [初始余额(可选)]
# 默认（自动找当前数据库，初始余额 1000）
python live_report.py

# 指定数据库 + 初始余额
python live_report.py "user_data/tradesv3.sqlite" 5000

# 指定输出 JSON 路径
python live_report.py "user_data/tradesv3.sqlite" 1000 "user_data/my_report.json"
"""

import sqlite3
import sys
import json
import math
import statistics
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path

import pandas as pd

from freqtrade.data.metrics import (
    calculate_calmar as ft_calculate_calmar,
    calculate_expectancy as ft_calculate_expectancy,
    calculate_max_drawdown as ft_calculate_max_drawdown,
    calculate_sharpe as ft_calculate_sharpe,
    calculate_sortino as ft_calculate_sortino,
    calculate_sqn as ft_calculate_sqn,
)


# ─── 配置 ─────────────────────────────────────────────────────────────────────
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else r"user_data/tradesv3_momentum_live.sqlite"
STARTING_BALANCE = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
OUTPUT_JSON = sys.argv[3] if len(sys.argv) > 3 else "user_data/live_report.json"


# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def fmt_duration(seconds: float) -> str:
    if seconds < 0:
        return "0:00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}:{m:02d}:00"


def fmt_timedelta(seconds: float) -> str:
    days = int(seconds // 86400)
    rem = seconds % 86400
    h = int(rem // 3600)
    m = int((rem % 3600) // 60)
    if days > 0:
        label = "day" if days == 1 else "days"
        return f"{days} {label}, {h:02d}:{m:02d}:00"
    return f"{h:02d}:{m:02d}:00"


def safe_div(a, b, default=0.0):
    return a / b if b != 0 else default


def calc_max_drawdown(equity_curve: list):
    """返回 (max_dd_abs, max_dd_pct, dd_start_idx, dd_end_idx, peak, trough)"""
    if not equity_curve:
        return 0, 0, 0, 0, STARTING_BALANCE, STARTING_BALANCE
    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0
    max_dd_pct = 0
    dd_start = 0
    dd_end = 0
    trough_val = equity_curve[0]
    peak_val = equity_curve[0]

    for i, val in enumerate(equity_curve):
        if val > peak:
            peak = val
            peak_idx = i
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd / peak
            dd_start = peak_idx
            dd_end = i
            peak_val = peak
            trough_val = val
    return max_dd, max_dd_pct, dd_start, dd_end, peak_val, trough_val


def trades_to_dataframe(trades_list: list) -> pd.DataFrame:
    if not trades_list:
        return pd.DataFrame(columns=["close_date", "profit_abs", "profit_ratio", "stake_amount", "is_short"])

    rows = []
    for trade in trades_list:
        rows.append(
            {
                "close_date": trade["close_date"],
                "profit_abs": trade["profit_abs"],
                "profit_ratio": trade["profit_ratio"],
                "stake_amount": trade["stake_amount"],
                "is_short": trade["is_short"],
            }
        )
    return pd.DataFrame(rows)


def build_total_row(key: str, trades_list: list, balance: float) -> dict:
    stats = per_group_stats(trades_list, balance)
    stats["key"] = key
    return stats


def print_bt_style_table(title: str, rows: list, key_label: str, key_width: int = 22):
    print(f"\n{title}")
    print(
        f"  {key_label:<{key_width}} {'交易次数':>8}  {'平均收益 %':>10}  {'总收益 USDT':>12}  {'总收益 %':>9}  {'平均持仓时间':>18}  {'胜  平  负  胜率%':>18}"
    )
    print(
        f"  {'-' * key_width} {'-' * 8}  {'-' * 10}  {'-' * 12}  {'-' * 9}  {'-' * 18}  {'-' * 18}"
    )
    for row in rows:
        winrate_pct = row["winrate"] * 100 if row.get("trades") else 0
        wdl = f"{row['wins']:>4} {row['draws']:>4} {row['losses']:>4} {winrate_pct:>6.1f}"
        print(
            f"  {str(row['key']):<{key_width}} {row['trades']:>8}  {row['profit_mean_pct']:>10.2f}  "
            f"{row['profit_total_abs']:>+12.3f}  {row['profit_total_pct']:>9.2f}  {row['duration_avg']:>18}  {wdl:>18}"
        )


def print_mix_tag_table(rows: list):
    print("\n混合标签 STATS")
    print(
        f"  {'入场标签':<22} {'出场原因':<22} {'交易次数':>8}  {'平均收益 %':>10}  {'总收益 USDT':>12}  {'总收益 %':>9}  {'平均持仓时间':>18}  {'胜  平  负  胜率%':>18}"
    )
    print(
        f"  {'-' * 22} {'-' * 22} {'-' * 8}  {'-' * 10}  {'-' * 12}  {'-' * 9}  {'-' * 18}  {'-' * 18}"
    )
    for row in rows:
        winrate_pct = row["winrate"] * 100 if row.get("trades") else 0
        wdl = f"{row['wins']:>4} {row['draws']:>4} {row['losses']:>4} {winrate_pct:>6.1f}"
        print(
            f"  {row['enter_tag']:<22} {row['exit_reason']:<22} {row['trades']:>8}  {row['profit_mean_pct']:>10.2f}  "
            f"{row['profit_total_abs']:>+12.3f}  {row['profit_total_pct']:>9.2f}  {row['duration_avg']:>18}  {wdl:>18}"
        )


def print_summary_metrics(rows: list):
    print("\n策略实盘汇总统计 (SUMMARY METRICS)")
    key_width = max(len(label) for label, _ in rows) + 2
    for label, value in rows:
        print(f"  {label:<{key_width}} {value}")


def per_group_stats(trades_list: list, balance: float) -> dict:
    """对一组交易计算回测格式的统计指标"""
    if not trades_list:
        return {}
    n = len(trades_list)
    profits_abs = [t["profit_abs"] for t in trades_list]
    profits_ratio = [t["profit_ratio"] for t in trades_list]
    wins = [t for t in trades_list if t["profit_abs"] > 0]
    losses = [t for t in trades_list if t["profit_abs"] <= 0]
    gross_profit = sum(t["profit_abs"] for t in wins)
    gross_loss = sum(abs(t["profit_abs"]) for t in losses)
    total_abs = sum(profits_abs)
    win_rate = safe_div(len(wins), n)
    durations = [t["duration_s"] for t in trades_list if t["duration_s"] is not None]
    duration_avg_s = statistics.mean(durations) if durations else 0

    df = trades_to_dataframe(trades_list)
    min_date = min((t["open_date"] for t in trades_list if t["open_date"]), default=None)
    max_date = max((t["close_date"] for t in trades_list if t["close_date"]), default=None)
    final_balance = balance + total_abs
    expectancy, expectancy_ratio = ft_calculate_expectancy(df)
    sharpe = ft_calculate_sharpe(df, min_date, max_date, balance)
    sortino = ft_calculate_sortino(df, min_date, max_date, balance)
    calmar = ft_calculate_calmar(df, min_date, max_date, balance)
    sqn = ft_calculate_sqn(df, balance)
    pf = safe_div(gross_profit, gross_loss)

    # max_drawdown within this group
    eq = [STARTING_BALANCE]
    for t in sorted(trades_list, key=lambda x: x["close_date"] or datetime.min):
        eq.append(eq[-1] + t["profit_abs"])
    max_dd_abs, max_dd_pct, *_ = calc_max_drawdown(eq)

    return {
        "trades": n,
        "profit_mean": safe_div(sum(profits_ratio), n),
        "profit_mean_pct": round(safe_div(sum(profits_ratio), n) * 100, 2),
        "profit_total_abs": round(total_abs, 8),
        "profit_total": round(safe_div(total_abs, balance), 8),
        "profit_total_pct": round(safe_div(total_abs, balance) * 100, 2),
        "duration_avg": fmt_timedelta(duration_avg_s),
        "duration_avg_s": duration_avg_s,
        "wins": len(wins),
        "draws": 0,
        "losses": len(losses),
        "winrate": win_rate,
        "expectancy": round(expectancy, 8),
        "expectancy_ratio": round(expectancy_ratio, 8),
        "sortino": round(sortino, 4),
        "sharpe": round(sharpe, 4),
        "calmar": round(calmar, 4),
        "sqn": sqn,
        "profit_factor": pf,
        "max_drawdown_account": max_dd_pct,
        "max_drawdown_abs": round(max_dd_abs, 8),
    }


# ─── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    base_query = """
        SELECT 
            id, pair, open_date, close_date,
            open_rate, close_rate,
            amount, stake_amount,
            COALESCE(close_profit, 0)        AS profit_ratio,
            COALESCE(close_profit_abs, 0)    AS profit_abs,
            exit_reason,
            enter_tag,
            is_short,
            is_open,
            fee_open_cost, fee_close_cost,
            funding_fees,
            leverage,
            initial_stop_loss   AS initial_stop_loss_abs,
            initial_stop_loss_pct AS initial_stop_loss_ratio,
            stop_loss           AS stop_loss_abs,
            stop_loss_pct       AS stop_loss_ratio,
            max_rate, min_rate
        FROM trades
        WHERE is_open = ?
        ORDER BY open_date
    """

    # 读取所有已平仓交易
    c.execute(base_query, (0,))
    raw_trades = c.fetchall()

    c.execute(base_query, (1,))
    raw_open_trades = c.fetchall()

    # 转换为可操作的 dict 列表
    trades = []
    for r in raw_trades:
        open_dt = datetime.fromisoformat(r["open_date"]).replace(tzinfo=timezone.utc) if r["open_date"] else None
        close_dt = datetime.fromisoformat(r["close_date"]).replace(tzinfo=timezone.utc) if r["close_date"] else None
        duration_s = (close_dt - open_dt).total_seconds() if open_dt and close_dt else None
        trades.append({
            "id": r["id"],
            "pair": r["pair"],
            "open_date": open_dt,
            "close_date": close_dt,
            "open_rate": r["open_rate"],
            "close_rate": r["close_rate"],
            "amount": r["amount"],
            "stake_amount": r["stake_amount"],
            "profit_ratio": r["profit_ratio"],
            "profit_abs": r["profit_abs"],
            "exit_reason": r["exit_reason"],
            "enter_tag": r["enter_tag"],
            "is_short": bool(r["is_short"]),
            "leverage": r["leverage"],
            "fee_open_cost": r["fee_open_cost"],
            "fee_close_cost": r["fee_close_cost"],
            "funding_fees": r["funding_fees"] or 0.0,
            "initial_stop_loss_abs": r["initial_stop_loss_abs"],
            "initial_stop_loss_ratio": r["initial_stop_loss_ratio"],
            "stop_loss_abs": r["stop_loss_abs"],
            "stop_loss_ratio": r["stop_loss_ratio"],
            "max_rate": r["max_rate"],
            "min_rate": r["min_rate"],
            "duration_s": duration_s,
        })

    open_trades = []
    now_utc = datetime.now(timezone.utc)
    for r in raw_open_trades:
        open_dt = datetime.fromisoformat(r["open_date"]).replace(tzinfo=timezone.utc) if r["open_date"] else None
        duration_s = (now_utc - open_dt).total_seconds() if open_dt else 0
        open_trades.append({
            "id": r["id"],
            "pair": r["pair"],
            "open_date": open_dt,
            "close_date": None,
            "open_rate": r["open_rate"],
            "close_rate": None,
            "amount": r["amount"],
            "stake_amount": r["stake_amount"],
            "profit_ratio": r["profit_ratio"],
            "profit_abs": r["profit_abs"],
            "exit_reason": "force_exit",
            "enter_tag": r["enter_tag"],
            "is_short": bool(r["is_short"]),
            "leverage": r["leverage"],
            "fee_open_cost": r["fee_open_cost"],
            "fee_close_cost": r["fee_close_cost"],
            "funding_fees": r["funding_fees"] or 0.0,
            "initial_stop_loss_abs": r["initial_stop_loss_abs"],
            "initial_stop_loss_ratio": r["initial_stop_loss_ratio"],
            "stop_loss_abs": r["stop_loss_abs"],
            "stop_loss_ratio": r["stop_loss_ratio"],
            "max_rate": r["max_rate"],
            "min_rate": r["min_rate"],
            "duration_s": duration_s,
        })

    conn.close()

    if not trades:
        print("没有已平仓交易。")
        return

    n = len(trades)
    profits_abs = [t["profit_abs"] for t in trades]
    profits_ratio = [t["profit_ratio"] for t in trades]
    wins = [t for t in trades if t["profit_abs"] > 0]
    losses = [t for t in trades if t["profit_abs"] <= 0]
    longs = [t for t in trades if not t["is_short"]]
    shorts = [t for t in trades if t["is_short"]]
    gross_profit = sum(p for p in profits_abs if p > 0)
    gross_loss = sum(abs(p) for p in profits_abs if p <= 0)
    total_pnl = sum(profits_abs)
    win_rate = safe_div(len(wins), n)

    # 日收益
    daily_pnl = defaultdict(float)
    daily_ratio = defaultdict(float)
    for t in trades:
        if t["close_date"]:
            day = t["close_date"].date()
            daily_pnl[day] += t["profit_abs"]
            daily_ratio[day] += t["profit_ratio"]
    # 时间范围
    first_open = min(t["open_date"] for t in trades)
    last_close = max(t["close_date"] for t in trades)
    n_days = max((last_close.date() - first_open.date()).days + 1, 1)

    # 权益曲线 (按 close_date 排序)
    equity = [STARTING_BALANCE]
    sorted_trades = sorted(trades, key=lambda x: x["close_date"])
    for t in sorted_trades:
        equity.append(equity[-1] + t["profit_abs"])
    final_balance = equity[-1]

    max_dd_abs, max_dd_pct, dd_start_idx, dd_end_idx, dd_peak, dd_trough = calc_max_drawdown(equity[1:])
    
    # 找到 drawdown 对应的日期（索引对应 sorted_trades）
    dd_start_date = sorted_trades[dd_start_idx]["close_date"] if dd_start_idx < len(sorted_trades) else last_close
    dd_end_date = sorted_trades[min(dd_end_idx, len(sorted_trades)-1)]["close_date"]

    # 每日数据
    daily_profits_sorted = sorted(daily_pnl.items())
    best_day = max(daily_profits_sorted, key=lambda x: x[1]) if daily_profits_sorted else (None, 0)
    worst_day = min(daily_profits_sorted, key=lambda x: x[1]) if daily_profits_sorted else (None, 0)
    winning_days = sum(1 for _, v in daily_profits_sorted if v > 0)
    losing_days = sum(1 for _, v in daily_profits_sorted if v < 0)
    draw_days = sum(1 for _, v in daily_profits_sorted if v == 0)

    # 持仓时间
    durations = [t["duration_s"] for t in trades if t["duration_s"] is not None]
    hold_avg = statistics.mean(durations) if durations else 0
    win_durations = [t["duration_s"] for t in wins if t["duration_s"] is not None]
    loss_durations = [t["duration_s"] for t in losses if t["duration_s"] is not None]
    win_hold_avg = statistics.mean(win_durations) if win_durations else 0
    loss_hold_avg = statistics.mean(loss_durations) if loss_durations else 0
    win_hold_min = min(win_durations) if win_durations else 0
    win_hold_max = max(win_durations) if win_durations else 0
    loss_hold_min = min(loss_durations) if loss_durations else 0
    loss_hold_max = max(loss_durations) if loss_durations else 0

    # 指标 - 使用 freqtrade 口径，和回测保持一致
    trades_df = trades_to_dataframe(trades)
    min_date = first_open
    max_date = last_close
    expectancy, expectancy_ratio = ft_calculate_expectancy(trades_df)
    sharpe = ft_calculate_sharpe(trades_df, min_date, max_date, STARTING_BALANCE)
    sortino = ft_calculate_sortino(trades_df, min_date, max_date, STARTING_BALANCE)
    calmar = ft_calculate_calmar(trades_df, min_date, max_date, STARTING_BALANCE)
    sqn = ft_calculate_sqn(trades_df, STARTING_BALANCE)
    pf = safe_div(gross_profit, gross_loss)

    # 连胜/连败
    max_consec_wins = max_consec_losses = cur_wins = cur_losses = 0
    for t in sorted_trades:
        if t["profit_abs"] > 0:
            cur_wins += 1
            cur_losses = 0
            max_consec_wins = max(max_consec_wins, cur_wins)
        else:
            cur_losses += 1
            cur_wins = 0
            max_consec_losses = max(max_consec_losses, cur_losses)

    # ── results_per_pair ──────────────────────────────────────────────────────
    pair_groups = defaultdict(list)
    for t in trades:
        pair_groups[t["pair"]].append(t)
    results_per_pair = []
    for pair, ts in sorted(pair_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = pair
        results_per_pair.append(stats)
    results_per_pair.append(build_total_row("TOTAL", trades, STARTING_BALANCE))

    pair_only = [x for x in results_per_pair if x["key"] != "TOTAL"]
    best_pair = max(pair_only, key=lambda x: x["profit_total_abs"])
    worst_pair = min(pair_only, key=lambda x: x["profit_total_abs"])

    # ── results_per_enter_tag ─────────────────────────────────────────────────
    tag_groups = defaultdict(list)
    for t in trades:
        tag_groups[t["enter_tag"] or "unknown"].append(t)
    results_per_enter_tag = []
    for tag, ts in sorted(tag_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = tag
        results_per_enter_tag.append(stats)
    results_per_enter_tag.append(build_total_row("TOTAL", trades, STARTING_BALANCE))

    # ── exit_reason_summary ───────────────────────────────────────────────────
    exit_groups = defaultdict(list)
    for t in trades:
        exit_groups[t["exit_reason"] or "unknown"].append(t)
    exit_reason_summary = []
    for reason, ts in sorted(exit_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = reason
        exit_reason_summary.append(stats)
    exit_reason_summary.append(build_total_row("TOTAL", trades, STARTING_BALANCE))

    # ── mix_tag_stats ────────────────────────────────────────────────────────────
    mix_tag_groups = defaultdict(list)
    for t in trades:
        mix_tag_groups[(t["enter_tag"] or "unknown", t["exit_reason"] or "unknown")].append(t)
    mix_tag_stats = []
    for (enter_tag, exit_reason), ts in sorted(
        mix_tag_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])
    ):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = f"{enter_tag}::{exit_reason}"
        stats["enter_tag"] = enter_tag
        stats["exit_reason"] = exit_reason
        mix_tag_stats.append(stats)
    total_mix = build_total_row("TOTAL", trades, STARTING_BALANCE)
    total_mix["enter_tag"] = "TOTAL"
    total_mix["exit_reason"] = ""
    mix_tag_stats.append(total_mix)

    left_open_trades = []
    for trade in open_trades:
        left_open_trades.append({
            "pair": trade["pair"],
            "stake_amount": trade["stake_amount"],
            "max_stake_amount": trade["stake_amount"],
            "amount": trade["amount"],
            "open_date": trade["open_date"].isoformat() if trade["open_date"] else None,
            "close_date": None,
            "open_rate": trade["open_rate"],
            "close_rate": None,
            "profit_ratio": trade["profit_ratio"],
            "profit_abs": trade["profit_abs"],
            "trade_duration": int(trade["duration_s"] / 60) if trade["duration_s"] else 0,
            "exit_reason": "force_exit",
            "enter_tag": trade["enter_tag"],
            "is_open": True,
            "is_short": trade["is_short"],
        })
    left_open_summary = []
    if open_trades:
        open_pair_groups = defaultdict(list)
        for trade in open_trades:
            open_pair_groups[trade["pair"]].append(trade)
        for pair, ts in sorted(open_pair_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
            stats = per_group_stats(ts, STARTING_BALANCE)
            stats["key"] = pair
            left_open_summary.append(stats)
        left_open_summary.append(build_total_row("TOTAL", open_trades, STARTING_BALANCE))

    # ── trades list (backtest 格式) ───────────────────────────────────────────
    bt_trades = []
    for t in sorted_trades:
        bt_trades.append({
            "pair": t["pair"],
            "stake_amount": t["stake_amount"],
            "max_stake_amount": t["stake_amount"],
            "amount": t["amount"],
            "open_date": t["open_date"].isoformat() if t["open_date"] else None,
            "close_date": t["close_date"].isoformat() if t["close_date"] else None,
            "open_rate": t["open_rate"],
            "close_rate": t["close_rate"],
            "fee_open": t["fee_open_cost"] / t["stake_amount"] if t["stake_amount"] else 0.0005,
            "fee_close": t["fee_close_cost"] / (t["stake_amount"] + t["profit_abs"]) if t["stake_amount"] else 0.0005,
            "trade_duration": int(t["duration_s"] / 60) if t["duration_s"] else 0,
            "profit_ratio": t["profit_ratio"],
            "profit_abs": t["profit_abs"],
            "exit_reason": t["exit_reason"],
            "initial_stop_loss_abs": t["initial_stop_loss_abs"],
            "initial_stop_loss_ratio": t["initial_stop_loss_ratio"],
            "stop_loss_abs": t["stop_loss_abs"],
            "stop_loss_ratio": t["stop_loss_ratio"],
            "min_rate": t["min_rate"],
            "max_rate": t["max_rate"],
            "is_open": False,
            "enter_tag": t["enter_tag"],
            "leverage": t["leverage"],
            "is_short": t["is_short"],
            "open_timestamp": int(t["open_date"].timestamp() * 1000) if t["open_date"] else 0,
            "close_timestamp": int(t["close_date"].timestamp() * 1000) if t["close_date"] else 0,
            "funding_fees": t["funding_fees"],
        })

    # ── daily_profit list ─────────────────────────────────────────────────────
    daily_profit_list = [
        {"date": str(d), "profit": round(v / STARTING_BALANCE, 8), "profit_abs": round(v, 8)}
        for d, v in sorted(daily_pnl.items())
    ]

    # ── 汇总 JSON ─────────────────────────────────────────────────────────────
    avg_stake = statistics.mean(t["stake_amount"] for t in trades)
    total_volume = sum(t["stake_amount"] for t in trades)

    result = {
        "trades": bt_trades,
        "locks": [],
        "best_pair": {"key": best_pair["key"], "trades": best_pair["trades"],
                      "profit_mean": best_pair["profit_mean"], "profit_mean_pct": best_pair["profit_mean_pct"],
                      "profit_total_abs": best_pair["profit_total_abs"]},
        "worst_pair": {"key": worst_pair["key"], "trades": worst_pair["trades"],
                       "profit_mean": worst_pair["profit_mean"], "profit_mean_pct": worst_pair["profit_mean_pct"],
                       "profit_total_abs": worst_pair["profit_total_abs"]},
        "results_per_pair": results_per_pair,
        "results_per_enter_tag": results_per_enter_tag,
        "exit_reason_summary": exit_reason_summary,
        "mix_tag_stats": mix_tag_stats,
        "left_open_trades": left_open_summary,
        "total_trades": n,
        "trade_count_long": len(longs),
        "trade_count_short": len(shorts),
        "total_volume": total_volume,
        "avg_stake_amount": avg_stake,
        "profit_mean": safe_div(sum(profits_ratio), n),
        "profit_median": statistics.median(profits_ratio),
        "profit_total": safe_div(total_pnl, STARTING_BALANCE),
        "profit_total_long": safe_div(sum(t["profit_abs"] for t in longs), STARTING_BALANCE),
        "profit_total_short": safe_div(sum(t["profit_abs"] for t in shorts), STARTING_BALANCE),
        "profit_total_abs": round(total_pnl, 8),
        "profit_total_long_abs": round(sum(t["profit_abs"] for t in longs), 8),
        "profit_total_short_abs": round(sum(t["profit_abs"] for t in shorts), 8),
        "expectancy": round(expectancy, 8),
        "expectancy_ratio": round(expectancy_ratio, 8),
        "sortino": round(sortino, 8),
        "sharpe": round(sharpe, 8),
        "calmar": round(calmar, 8),
        "sqn": sqn,
        "profit_factor": pf,
        "backtest_start": first_open.strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_end": last_close.strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_days": n_days,
        "trades_per_day": round(n / n_days, 2),
        "stake_amount": "unlimited",
        "stake_currency": "USDT",
        "starting_balance": STARTING_BALANCE,
        "final_balance": round(final_balance, 8),
        "max_open_trades_setting": 10,
        "timeframe": "1h",
        "stoploss": -0.1,
        "trailing_stop": False,
        "wins": len(wins),
        "losses": len(losses),
        "draws": 0,
        "winrate": win_rate,
        "winning_days": winning_days,
        "losing_days": losing_days,
        "draw_days": draw_days,
        "holding_avg": fmt_duration(hold_avg),
        "holding_avg_s": hold_avg,
        "duration_avg": fmt_timedelta(hold_avg),
        "duration_avg_s": hold_avg,
        "winner_holding_min": fmt_duration(win_hold_min),
        "winner_holding_min_s": win_hold_min,
        "winner_holding_max": fmt_duration(win_hold_max),
        "winner_holding_max_s": win_hold_max,
        "winner_holding_avg": fmt_duration(win_hold_avg),
        "winner_holding_avg_s": win_hold_avg,
        "loser_holding_min": fmt_duration(loss_hold_min),
        "loser_holding_min_s": loss_hold_min,
        "loser_holding_max": fmt_duration(loss_hold_max),
        "loser_holding_max_s": loss_hold_max,
        "loser_holding_avg": fmt_duration(loss_hold_avg),
        "loser_holding_avg_s": loss_hold_avg,
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "max_drawdown_account": max_dd_pct,
        "max_relative_drawdown": max_dd_pct,
        "max_drawdown_abs": round(max_dd_abs, 8),
        "drawdown_start": dd_start_date.strftime("%Y-%m-%d %H:%M:%S") if dd_start_date else "",
        "drawdown_end": dd_end_date.strftime("%Y-%m-%d %H:%M:%S") if dd_end_date else "",
        "max_drawdown_high": round(dd_peak, 8),
        "max_drawdown_low": round(dd_trough, 8),
        "backtest_best_day": round(best_day[1] / STARTING_BALANCE, 8),
        "backtest_worst_day": round(worst_day[1] / STARTING_BALANCE, 8),
        "backtest_best_day_abs": round(best_day[1], 8),
        "backtest_worst_day_abs": round(worst_day[1], 8),
        "daily_profit": daily_profit_list,
        "source": "live_database",
        "db_path": DB_PATH,
        "sample_warning": "Live sample is shorter than 30 days; annualized metrics may be unstable."
        if n_days < 30
        else "",
    }

    # ── 保存 JSON ─────────────────────────────────────────────────────────────
    Path(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # ─── 终端输出（与 freqtrade 回测格式对齐） ────────────────────────────────
    SEP = "=" * 70
    print(SEP)
    try:
        print(f"{'实盘分析报告 (Live Trading Report)':^70}")
    except (UnicodeEncodeError, OSError):
        print(f"{'Live Trading Report':^70}")
    print(f"  数据库: {DB_PATH}")
    print(f"  分析周期: {first_open.strftime('%Y-%m-%d %H:%M')} → {last_close.strftime('%Y-%m-%d %H:%M')}  ({n_days} 天)")
    print(f"  初始余额: {STARTING_BALANCE:.2f} USDT  →  终止余额: {final_balance:.2f} USDT")
    print(SEP)

    if n_days < 30:
        print("  [WARN] 实盘样本不足 30 天，Sharpe / Sortino / Calmar 等风险指标会明显失真，解读时请结合样本期长度。")

    print_bt_style_table("策略实盘明细报告 (LIVE REPORT)", results_per_pair, "交易对")
    if left_open_summary:
        print_bt_style_table("未平仓交易报告 (LEFT OPEN TRADES REPORT)", left_open_summary, "交易对")
    else:
        print("\n未平仓交易报告 (LEFT OPEN TRADES REPORT)")
        print("  当前无未平仓交易。")
    print_bt_style_table("入场标签 STATS", results_per_enter_tag, "入场标签", key_width=20)
    print_bt_style_table("出场原因 STATS", exit_reason_summary, "出场原因", key_width=20)
    print_mix_tag_table(mix_tag_stats)

    best_trade = max(trades, key=lambda x: x["profit_ratio"])
    worst_trade = min(trades, key=lambda x: x["profit_ratio"])
    min_balance = min(equity)
    max_balance = max(equity)
    summary_rows = [
        ("实盘起始时间", first_open.strftime("%Y-%m-%d %H:%M:%S")),
        ("实盘结束时间", last_close.strftime("%Y-%m-%d %H:%M:%S")),
        ("Trading Mode", "Isolated Futures"),
        ("最大并发交易数", 10),
        ("", ""),
        ("总计 / 日均交易次数", f"{n} / {round(n / n_days, 2)}"),
        ("初始账户余额", f"{STARTING_BALANCE:.2f} USDT"),
        ("最终账户余额", f"{final_balance:.2f} USDT"),
        ("净利润 (绝对值)", f"{total_pnl:.3f} USDT"),
        ("总收益率 %", f"{safe_div(total_pnl, STARTING_BALANCE) * 100:.2f}%"),
        ("索提诺比率 (Sortino)", f"{sortino:.2f}"),
        ("夏普比率 (Sharpe)", f"{sharpe:.2f}"),
        ("卡玛比率 (Calmar)", f"{calmar:.2f}"),
        ("系统获利指标 (SQN)", f"{sqn:.2f}"),
        ("获利因子 (Profit Factor)", f"{pf:.2f}"),
        ("交易期望值 (Ratio)", f"{expectancy:.2f} ({expectancy_ratio:.2f})"),
        ("日均利润", f"{safe_div(total_pnl, n_days):.3f} USDT"),
        ("平均单笔头寸", f"{avg_stake:.3f} USDT"),
        ("总交易成交额", f"{total_volume:.3f} USDT"),
        ("", ""),
        ("Long / Short trades", f"{len(longs)} / {len(shorts)}"),
        (
            "Long / Short profit %",
            f"{safe_div(sum(t['profit_abs'] for t in longs), STARTING_BALANCE) * 100:.2f}% / {safe_div(sum(t['profit_abs'] for t in shorts), STARTING_BALANCE) * 100:.2f}%",
        ),
        (
            "Long / Short profit USDT",
            f"{sum(t['profit_abs'] for t in longs):.3f} / {sum(t['profit_abs'] for t in shorts):.3f}",
        ),
        ("", ""),
        ("表现最佳交易对", f"{best_pair['key']} {best_pair['profit_total_pct']:.2f}%"),
        ("表现最差交易对", f"{worst_pair['key']} {worst_pair['profit_total_pct']:.2f}%"),
        ("单笔最佳交易", f"{best_trade['pair']} {best_trade['profit_ratio'] * 100:.2f}%"),
        ("单笔最差交易", f"{worst_trade['pair']} {worst_trade['profit_ratio'] * 100:.2f}%"),
        ("获利最高日", f"{best_day[1]:.3f} USDT"),
        ("亏损最高日", f"{worst_day[1]:.3f} USDT"),
        ("盈利/持平/亏损天数", f"{winning_days} / {draw_days} / {losing_days}"),
        (
            "获利单 持仓最短/最长/平均时间",
            f"{fmt_timedelta(win_hold_min)} / {fmt_timedelta(win_hold_max)} / {fmt_timedelta(win_hold_avg)}",
        ),
        (
            "亏损单 持仓最短/最长/平均时间",
            f"{fmt_timedelta(loss_hold_min)} / {fmt_timedelta(loss_hold_max)} / {fmt_timedelta(loss_hold_avg)}",
        ),
        ("最大连续盈利 / 亏损次数", f"{max_consec_wins} / {max_consec_losses}"),
        ("被拒绝的入场信号", "N/A"),
        ("入场/出场超时次数", "N/A / N/A"),
        ("", ""),
        ("账户余额最小值", f"{min_balance:.3f} USDT"),
        ("账户余额最大值", f"{max_balance:.3f} USDT"),
        ("最大账户回撤率 (Underwater)", f"{max_dd_pct * 100:.2f}%"),
        ("最大回撤额 (绝对值)", f"{max_dd_abs:.3f} USDT ({max_dd_pct * 100:.2f}%)"),
        ("回撤持时", f"{fmt_timedelta((dd_end_date - dd_start_date).total_seconds()) if dd_start_date and dd_end_date else 'N/A'}"),
        ("回撤开始时的利润额", f"{dd_peak - STARTING_BALANCE:.3f} USDT"),
        ("回撤结束时的利润额", f"{dd_trough - STARTING_BALANCE:.3f} USDT"),
        ("回撤开始日期", dd_start_date.strftime("%Y-%m-%d %H:%M:%S") if dd_start_date else "N/A"),
        ("回撤结束日期", dd_end_date.strftime("%Y-%m-%d %H:%M:%S") if dd_end_date else "N/A"),
        ("市场涨跌幅 (Market Change)", "N/A"),
    ]
    print_summary_metrics(summary_rows)

    print(f"\n  [OK] JSON 报告已保存: {OUTPUT_JSON}")
    print(SEP)


if __name__ == "__main__":
    main()
