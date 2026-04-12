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


# ─── 配置 ─────────────────────────────────────────────────────────────────────
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else r"user_data/tradesv3_momentum_live (1).sqlite"
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
        return f"{days} days {h:02d}:{m:02d}:00"
    return f"{h}:{m:02d}:00"


def safe_div(a, b, default=0.0):
    return a / b if b != 0 else default


def calc_sortino(daily_profits: list) -> float:
    """Sortino ratio (annualized, risk-free=0)"""
    if len(daily_profits) < 2:
        return 0.0
    mean = statistics.mean(daily_profits)
    neg = [x for x in daily_profits if x < 0]
    if not neg:
        return 999.0
    downside_std = math.sqrt(sum(x**2 for x in neg) / len(daily_profits))
    if downside_std == 0:
        return 999.0
    return (mean / downside_std) * math.sqrt(365)


def calc_sharpe(daily_profits: list) -> float:
    """Sharpe ratio (annualized, risk-free=0)"""
    if len(daily_profits) < 2:
        return 0.0
    mean = statistics.mean(daily_profits)
    std = statistics.stdev(daily_profits)
    if std == 0:
        return 999.0
    return (mean / std) * math.sqrt(365)


def calc_calmar(daily_profits: list, total_profit_abs: float, max_dd_abs: float) -> float:
    if max_dd_abs == 0:
        return 999.0
    # CAGR / Max_Drawdown_pct
    # 简化: 用 total_profit_abs 折算
    n_days = len(daily_profits) if daily_profits else 1
    cagr = (1 + total_profit_abs / STARTING_BALANCE) ** (365 / n_days) - 1
    return safe_div(cagr * 100, max_dd_abs / STARTING_BALANCE * 100)


def calc_cagr(profit_abs: float, n_days: int) -> float:
    if n_days <= 0:
        return 0.0
    return ((1 + profit_abs / STARTING_BALANCE) ** (365 / n_days) - 1) * 100


def calc_sqn(profits: list) -> float:
    """System Quality Number = (mean/std) * sqrt(n)"""
    if len(profits) < 2:
        return 0.0
    mean = statistics.mean(profits)
    std = statistics.stdev(profits)
    if std == 0:
        return 0.0
    return round((mean / std) * math.sqrt(len(profits)), 4)


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
    avg_win = safe_div(sum(t["profit_ratio"] for t in wins), len(wins)) if wins else 0
    avg_loss = safe_div(sum(t["profit_ratio"] for t in losses), len(losses)) if losses else 0
    expectancy = win_rate * avg_win - (1 - win_rate) * abs(avg_loss)
    expectancy_ratio = safe_div(expectancy, abs(avg_loss)) if avg_loss else 0

    durations = [t["duration_s"] for t in trades_list if t["duration_s"] is not None]
    duration_avg_s = statistics.mean(durations) if durations else 0

    # 简单日收益（按开仓日期分组）
    daily = defaultdict(float)
    for t in trades_list:
        if t["close_date"]:
            day = t["close_date"].date()
            daily[day] += t["profit_ratio"]
    daily_list = list(daily.values())

    sharpe = calc_sharpe(daily_list)
    sortino = calc_sortino(daily_list)
    n_days = max((max(daily.keys()) - min(daily.keys())).days + 1, 1) if daily else 1
    cagr = calc_cagr(total_abs, n_days)
    calmar = safe_div(cagr, safe_div(abs(gross_loss), balance) * 100)
    sqn = calc_sqn(profits_abs)
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
        "duration_avg": fmt_duration(duration_avg_s),
        "wins": len(wins),
        "draws": 0,
        "losses": len(losses),
        "winrate": win_rate,
        "cagr": cagr,
        "expectancy": expectancy,
        "expectancy_ratio": expectancy_ratio,
        "sortino": sortino,
        "sharpe": sharpe,
        "calmar": calmar,
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

    # 读取所有已平仓交易
    c.execute("""
        SELECT 
            id, pair, open_date, close_date,
            open_rate, close_rate,
            amount, stake_amount,
            close_profit        AS profit_ratio,
            close_profit_abs    AS profit_abs,
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
        WHERE is_open = 0
        ORDER BY close_date
    """)
    raw_trades = c.fetchall()

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
    daily_ratio_list = list(daily_ratio.values())

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

    # 指标
    avg_win_ratio = safe_div(sum(t["profit_ratio"] for t in wins), len(wins)) if wins else 0
    avg_loss_ratio = safe_div(sum(t["profit_ratio"] for t in losses), len(losses)) if losses else 0
    expectancy = win_rate * avg_win_ratio - (1 - win_rate) * abs(avg_loss_ratio)
    expectancy_ratio = safe_div(expectancy, abs(avg_loss_ratio)) if avg_loss_ratio else 0
    sharpe = calc_sharpe(daily_ratio_list)
    sortino = calc_sortino(daily_ratio_list)
    cagr_val = calc_cagr(total_pnl, n_days)
    calmar = safe_div(cagr_val, max_dd_pct * 100) if max_dd_pct > 0 else 999.0
    sqn = calc_sqn(profits_abs)
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

    best_pair = max(results_per_pair, key=lambda x: x["profit_total_abs"])
    worst_pair = min(results_per_pair, key=lambda x: x["profit_total_abs"])

    # ── results_per_enter_tag ─────────────────────────────────────────────────
    tag_groups = defaultdict(list)
    for t in trades:
        tag_groups[t["enter_tag"] or "unknown"].append(t)
    results_per_enter_tag = []
    for tag, ts in sorted(tag_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = tag
        results_per_enter_tag.append(stats)

    # ── exit_reason_summary ───────────────────────────────────────────────────
    exit_groups = defaultdict(list)
    for t in trades:
        exit_groups[t["exit_reason"] or "unknown"].append(t)
    exit_reason_summary = []
    for reason, ts in sorted(exit_groups.items(), key=lambda x: -sum(t["profit_abs"] for t in x[1])):
        stats = per_group_stats(ts, STARTING_BALANCE)
        stats["key"] = reason
        exit_reason_summary.append(stats)

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
        "total_trades": n,
        "trade_count_long": len(longs),
        "trade_count_short": len(shorts),
        "total_volume": total_volume,
        "avg_stake_amount": avg_stake,
        "profit_mean": safe_div(sum(profits_ratio), n),
        "profit_median": sorted(profits_ratio)[n // 2],
        "profit_total": safe_div(total_pnl, STARTING_BALANCE),
        "profit_total_long": safe_div(sum(t["profit_abs"] for t in longs), STARTING_BALANCE),
        "profit_total_short": safe_div(sum(t["profit_abs"] for t in shorts), STARTING_BALANCE),
        "profit_total_abs": round(total_pnl, 8),
        "profit_total_long_abs": round(sum(t["profit_abs"] for t in longs), 8),
        "profit_total_short_abs": round(sum(t["profit_abs"] for t in shorts), 8),
        "cagr": cagr_val,
        "expectancy": expectancy,
        "expectancy_ratio": expectancy_ratio,
        "sortino": sortino,
        "sharpe": sharpe,
        "calmar": calmar,
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
    }

    # ── 保存 JSON ─────────────────────────────────────────────────────────────
    Path(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # ─── 终端输出（与 freqtrade 回测格式对齐） ────────────────────────────────
    SEP = "=" * 70
    print(SEP)
    print(f"{'실盘分析报告 (Live Trading Report)':^70}")
    print(f"  数据库: {DB_PATH}")
    print(f"  分析周期: {first_open.strftime('%Y-%m-%d %H:%M')} → {last_close.strftime('%Y-%m-%d %H:%M')}  ({n_days} 天)")
    print(f"  初始余额: {STARTING_BALANCE:.2f} USDT  →  终止余额: {final_balance:.2f} USDT")
    print(SEP)

    print(f"\n{'─── 核心指标 ─':{'─'}<50}")
    rows = [
        ("总交易数",         f"{n}  (多: {len(longs)}  空: {len(shorts)})"),
        ("胜率",            f"{win_rate * 100:.2f}%  (胜: {len(wins)}  负: {len(losses)})"),
        ("总 PnL",          f"{total_pnl:+.2f} USDT  ({total_pnl / STARTING_BALANCE * 100:+.2f}%)"),
        ("Long PnL",        f"{sum(t['profit_abs'] for t in longs):+.2f} USDT"),
        ("Short PnL",       f"{sum(t['profit_abs'] for t in shorts):+.2f} USDT"),
        ("CAGR",            f"{cagr_val:.2f}%"),
        ("Expectancy",      f"{expectancy * 100:.4f}%  (ratio: {expectancy_ratio:.4f})"),
        ("Sharpe",          f"{sharpe:.4f}"),
        ("Sortino",         f"{sortino:.4f}"),
        ("Calmar",          f"{calmar:.4f}"),
        ("SQN",             f"{sqn:.4f}"),
        ("Profit Factor",   f"{pf:.4f}"),
        ("最大回撤",        f"{max_dd_abs:.2f} USDT  ({max_dd_pct * 100:.2f}%)"),
        ("最佳单日",        f"{best_day[1]:+.2f} USDT  ({best_day[0]})"),
        ("最差单日",        f"{worst_day[1]:+.2f} USDT  ({worst_day[0]})"),
        ("盈利天/亏损天",   f"{winning_days} / {losing_days}"),
        ("平均持仓",        fmt_timedelta(hold_avg)),
        ("最大连胜/连败",   f"{max_consec_wins} / {max_consec_losses}"),
    ]
    for label, value in rows:
        print(f"  {label:<18}: {value}")

    # ── 出场原因 ──────────────────────────────────────────────────────────────
    print(f"\n{'─── 出场原因 ─':{'─'}<70}")
    print(f"  {'出场原因':<28} {'笔数':>5}  {'PnL(USDT)':>10}  {'均盈亏%':>8}  {'胜率':>7}  {'PF':>6}")
    print(f"  {'-'*28} {'-'*5}  {'-'*10}  {'-'*8}  {'-'*7}  {'-'*6}")
    for s in exit_reason_summary:
        wr = s["wins"] / s["trades"] * 100 if s["trades"] else 0
        print(f"  {s['key']:<28} {s['trades']:>5}  {s['profit_total_abs']:>+10.2f}  {s['profit_mean_pct']:>+7.2f}%  {wr:>6.1f}%  {s['profit_factor']:>6.3f}")

    # ── 入场标签 ──────────────────────────────────────────────────────────────
    print(f"\n{'─── 入场标签 ─':{'─'}<70}")
    print(f"  {'入场标签':<28} {'笔数':>5}  {'PnL(USDT)':>10}  {'均盈亏%':>8}  {'胜率':>7}  {'期望值':>8}")
    print(f"  {'-'*28} {'-'*5}  {'-'*10}  {'-'*8}  {'-'*7}  {'-'*8}")
    for s in results_per_enter_tag:
        wr = s["wins"] / s["trades"] * 100 if s["trades"] else 0
        print(f"  {s['key']:<28} {s['trades']:>5}  {s['profit_total_abs']:>+10.2f}  {s['profit_mean_pct']:>+7.2f}%  {wr:>6.1f}%  {s['expectancy']:>+8.5f}")

    # ── 最差币种 Top5 ─────────────────────────────────────────────────────────
    print(f"\n{'─── 最差币种 Top 5 ─':{'─'}<70}")
    print(f"  {'币种':<22} {'笔数':>5}  {'PnL(USDT)':>10}  {'均盈亏%':>8}  {'胜率':>7}  {'最大DD':>8}")
    print(f"  {'-'*22} {'-'*5}  {'-'*10}  {'-'*8}  {'-'*7}  {'-'*8}")
    worst5 = sorted(results_per_pair, key=lambda x: x["profit_total_abs"])[:5]
    for s in worst5:
        wr = s["wins"] / s["trades"] * 100 if s["trades"] else 0
        print(f"  {s['key']:<22} {s['trades']:>5}  {s['profit_total_abs']:>+10.2f}  {s['profit_mean_pct']:>+7.2f}%  {wr:>6.1f}%  {s['max_drawdown_abs']:>+8.2f}")

    # ── 最佳币种 Top5 ─────────────────────────────────────────────────────────
    print(f"\n{'─── 最佳币种 Top 5 ─':{'─'}<70}")
    print(f"  {'币种':<22} {'笔数':>5}  {'PnL(USDT)':>10}  {'均盈亏%':>8}  {'胜率':>7}  {'PF':>6}")
    print(f"  {'-'*22} {'-'*5}  {'-'*10}  {'-'*8}  {'-'*7}  {'-'*6}")
    best5 = sorted(results_per_pair, key=lambda x: -x["profit_total_abs"])[:5]
    for s in best5:
        wr = s["wins"] / s["trades"] * 100 if s["trades"] else 0
        print(f"  {s['key']:<22} {s['trades']:>5}  {s['profit_total_abs']:>+10.2f}  {s['profit_mean_pct']:>+7.2f}%  {wr:>6.1f}%  {s['profit_factor']:>6.3f}")

    # ── 按日收益 ──────────────────────────────────────────────────────────────
    print(f"\n{'─── 每日收益 ─':{'─'}<70}")
    print(f"  {'日期':<12} {'PnL(USDT)':>12}  {'收益率':>8}  {'笔数':>5}")
    print(f"  {'-'*12} {'-'*12}  {'-'*8}  {'-'*5}")
    for day, pnl in sorted(daily_pnl.items()):
        cnt = sum(1 for t in trades if t["close_date"] and t["close_date"].date() == day)
        pct = pnl / STARTING_BALANCE * 100
        flag = "▲" if pnl > 0 else "▼"
        print(f"  {str(day):<12} {pnl:>+11.2f}  {pct:>+7.2f}%  {cnt:>5}  {flag}")

    print(f"\n  ✅ JSON 报告已保存: {OUTPUT_JSON}")
    print(SEP)


if __name__ == "__main__":
    main()
