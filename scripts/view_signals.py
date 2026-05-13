"""
信号日志查看工具

用法：
  python scripts/view_signals.py                    # 查看今天的信号
  python scripts/view_signals.py 2026-05-13         # 查看指定日期
  python scripts/view_signals.py --stats             # 只看统计
  python scripts/view_signals.py --pair AAVE         # 按币种筛选
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

LOG_DIR = Path("user_data/logs")


def load_signals(date_str: str) -> list[dict]:
    """加载指定日期的信号日志"""
    filepath = LOG_DIR / f"signals_{date_str}.jsonl"
    if not filepath.exists():
        print(f"❌ 未找到信号日志: {filepath}")
        return []
    signals = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return signals


def format_time(t: str) -> str:
    """格式化时间，只保留 月-日 时:分"""
    try:
        # 处理多种时间格式
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"]:
            try:
                dt = datetime.strptime(t[:19], fmt[:len(t[:19])+2])
                return dt.strftime("%m-%d %H:%M")
            except ValueError:
                continue
        return t[5:16] if len(t) > 16 else t
    except Exception:
        return t


def print_stats(entries: list[dict], exits: list[dict]):
    """打印统计信息"""
    print("═" * 55)
    print("  📊 信号统计")
    print("═" * 55)

    # 入场统计
    gmgn_entries = [e for e in entries if e.get("signal_source") == "gmgn"]
    tech_entries = [e for e in entries if e.get("signal_source") == "tech"]
    print(f"\n  入场信号: {len(entries)} 个")
    print(f"    🟢 GMGN+技术面: {len(gmgn_entries)}")
    print(f"    🟡 纯技术面:    {len(tech_entries)}")

    # 出场统计
    exit_reasons = Counter(e.get("exit_reason", "unknown") for e in exits)
    print(f"\n  出场信号: {len(exits)} 个")
    for reason, count in exit_reasons.most_common():
        label = {
            "smart_money_exit": "聪明钱撤退",
            "smart_money_decline": "聪明钱衰退",
            "sniper_spike": "狙击手激增",
            "security_deteriorated": "安全恶化",
            "honeypot_detected": "貔貅转化",
            "fresh_wallet_spike": "新钱包暴增",
            "rsi_overbought": "RSI超买",
            "volume_divergence": "量价背离",
            "profit_protect_tier1": "利润保护15%",
            "profit_protect_tier2": "利润保护25%",
            "profit_protect_tier3": "利润保护40%",
            "time_stop_7d": "7天时间止损",
            "trailing_stop": "移动止损",
            "stoploss": "硬止损",
        }.get(reason, reason)
        print(f"    {label}: {count}")

    # 盈亏统计（有 profit_pct 的出场信号）
    profits = [e.get("profit_pct", 0) for e in exits if "profit_pct" in e]
    if profits:
        avg_profit = sum(profits) / len(profits)
        win_count = sum(1 for p in profits if p > 0)
        print(f"\n  盈亏统计 (有记录的):")
        print(f"    胜率: {win_count}/{len(profits)} ({win_count/len(profits)*100:.0f}%)")
        print(f"    平均利润: {avg_profit:+.1f}%")

    print()


def print_entries(entries: list[dict]):
    """打印入场信号"""
    if not entries:
        print("  无入场信号\n")
        return

    print("  📈 入场信号")
    print("  " + "─" * 53)
    print(f"  {'时间':<12} {'币种':<10} {'来源':<8} {'分数':<10} {'价格':<12} {'详情'}")
    print("  " + "─" * 53)

    for e in entries:
        t = format_time(e.get("time", ""))
        pair = e.get("pair", "").split("/")[0]
        src = e.get("signal_source", "tech")
        emoji = "🟢" if src == "gmgn" else "🟡"
        score_info = e.get("score", {})
        score_str = f"{score_info.get('total', 0):.0f}/{score_info.get('max', 60)}"
        price = e.get("price", 0)
        tech = e.get("tech", {})
        detail = f"BB={tech.get('bb_width_pctl', 0):.2f} 量比={tech.get('volume_ratio', 0):.2f} RSI={tech.get('rsi', 0):.0f}"

        if src == "gmgn":
            gmgn = e.get("gmgn", {})
            detail += f" SM={gmgn.get('smart_money_count', 0)}"

        print(f"  {t:<12} {pair:<10} {emoji} {src:<6} {score_str:<10} ${price:<11.4f} {detail}")

    print()


def print_exits(exits: list[dict]):
    """打印出场信号"""
    if not exits:
        print("  无出场信号\n")
        return

    print("  📉 出场信号")
    print("  " + "─" * 53)

    for e in exits:
        t = format_time(e.get("time", ""))
        pair = e.get("pair", "").split("/")[0]
        reason = e.get("exit_reason", "unknown")
        price = e.get("price", 0)
        profit = e.get("profit_pct")
        exit_src = e.get("exit_source", "tech")
        emoji = "🟢" if exit_src == "gmgn" else "🟡"

        profit_str = f" {profit:+.1f}%" if profit is not None else ""
        print(f"  {t:<12} {pair:<10} {emoji} {reason:<25} ${price:.4f}{profit_str}")

    print()


def main():
    # 解析参数
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    stats_only = False
    pair_filter = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--stats":
            stats_only = True
        elif args[i] == "--pair" and i + 1 < len(args):
            pair_filter = args[i + 1].upper()
            i += 1
        elif not args[i].startswith("--"):
            date_str = args[i]
        i += 1

    signals = load_signals(date_str)
    if not signals:
        return

    # 按币种筛选
    if pair_filter:
        signals = [s for s in signals if pair_filter in s.get("pair", "").upper()]
        if not signals:
            print(f"❌ 未找到 {pair_filter} 的信号")
            return

    # 分类
    entries = [s for s in signals if s.get("action") == "entry"]
    exits = [s for s in signals if s.get("action") == "exit"]

    # 输出
    print(f"\n{'═' * 55}")
    print(f"  信号日志  {date_str}")
    if pair_filter:
        print(f"  筛选: {pair_filter}")
    print(f"{'═' * 55}\n")

    print_stats(entries, exits)

    if not stats_only:
        print_entries(entries)
        print_exits(exits)


if __name__ == "__main__":
    main()
