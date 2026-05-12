"""
bt_parse.py — Freqtrade 回测结果全量解析工具
用法:
    python scripts/bt_parse.py [zip_path]                      # 指定文件
    python scripts/bt_parse.py                                 # 自动使用最新回测
    python scripts/bt_parse.py --trades                        # 额外输出每笔交易明细
    python scripts/bt_parse.py [zip_path] --out <file>         # 输出到 UTF-8 文件（推荐，避免 Windows 终端乱码）
    python scripts/bt_parse.py [zip_path] --out <file> --trades  # 含交易明细输出到文件

示例 (Windows PowerShell):
    conda activate freqAi ; python scripts/bt_parse.py --out scripts/bt_out.txt
    conda activate freqAi ; python scripts/bt_parse.py user_data/backtest_results/xxx.zip --out scripts/bt_out.txt

覆盖维度:
    1. 策略概览
    2. 收益指标
    3. 风险指标
    4. 风险调整收益 (Sharpe/Sortino/Calmar/SQN)
    5. 交易统计
    6. 仓位统计
    7. 品种盈亏穿透 (results_per_pair)
    8. 入场标签维度 (results_per_enter_tag)
    9. 出场原因维度 (exit_reason_summary)
   10. 混合标签维度 (mix_tag_stats)
   11. 年度业绩分析 (periodic_breakdown year)
   12. 月度盈亏全量 (periodic_breakdown month)
   13. 星期分布分析 (periodic_breakdown weekday)
   14. 回撤详情
   15. 未平仓持仓
   16. 策略参数
   17. 综合诊断评分
   [可选] 交易明细列表
"""

import sys
import json
import zipfile
from pathlib import Path

# 强制 stdout 使用 UTF-8，避免 Windows GBK 终端编码错误
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def pct(v, decimals=2):
    return f"{round(v * 100, decimals)}%" if isinstance(v, (int, float)) else str(v)

def usd(v, decimals=2):
    return f"{round(v, decimals)} USDT"

def bar(val, scale=20):
    """简易 ASCII 柱状图"""
    n = min(int(abs(val) / scale), 20)
    ch = "█" if val >= 0 else "▓"
    return ch * n


# ─────────────────────────────────────────────
# 主解析类
# ─────────────────────────────────────────────

class BacktestParser:

    def __init__(self, zip_path: str):
        self.zip_path = Path(zip_path)
        self.data = self._load()
        self.strat_name = list(self.data["strategy"].keys())[0]
        self.s = self.data["strategy"][self.strat_name]
        self.trades = self.s.get("trades", [])
        self.show_trades = "--trades" in sys.argv

    def _load(self):
        with zipfile.ZipFile(self.zip_path, "r") as z:
            json_file = [f for f in z.namelist() if f.endswith(".json")][0]
            with z.open(json_file) as f:
                return json.load(f)

    # ─── 通用标签表格渲染 ───

    def _print_tag_table(self, data: list, title: str, key_label: str = "标签"):
        """
        通用表格渲染，适用于:
          results_per_pair / results_per_enter_tag /
          exit_reason_summary / mix_tag_stats
        """
        if not data:
            print(f"\n{title}: 无数据")
            return
        print(f"\n{title}")
        hdr = (f"  {'#':>3}  {key_label:<28} {'笔数':>6} {'胜率':>7} "
               f"{'均收益%':>8} {'总盈亏':>10} {'Sharpe':>8} "
               f"{'Sortino':>8} {'Calmar':>8} {'期望值':>9} {'最大回撤%':>10}")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for i, item in enumerate(data, 1):
            key = item.get("key", "?")
            if isinstance(key, list):
                key = " × ".join(key)
            pnl = item.get("profit_total_abs", 0)
            flag = "✓" if pnl > 0 else "✗"
            key_str = f"{flag} {str(key)}"
            print(
                f"  {i:>3}  {key_str:<28} "
                f"{item.get('trades', 0):>6} "
                f"{pct(item.get('winrate', 0)):>7} "
                f"{round(item.get('profit_mean', 0)*100, 3):>8} "
                f"{round(pnl, 2):>10} "
                f"{round(item.get('sharpe', 0), 3):>8} "
                f"{round(item.get('sortino', 0), 3):>8} "
                f"{round(item.get('calmar', 0), 3):>8} "
                f"{round(item.get('expectancy', 0), 4):>9} "
                f"{pct(item.get('max_drawdown_account', 0)):>10}"
            )

    # ─── 章节1：基础概览 ───

    def section_overview(self):
        s = self.s
        days = s.get("backtest_days", 0)
        years = round(days / 365, 2)
        print("=" * 70)
        print(f"  策略: {self.strat_name}")
        print(f"  回测区间: {s.get('backtest_start')} ~ {s.get('backtest_end')}")
        print(f"  回测天数: {days} 天 ({years} 年)")
        print(f"  时间框架: {s.get('timeframe')}  |  交易对数: {len(s.get('pairlist', []))}")
        print(f"  初始资金: {usd(s.get('starting_balance', 1000))}  |  最终余额: {usd(s.get('final_balance', 0))}")
        print(f"  手续费: futures模式 (fee见config)  |  杠杆: {s.get('leverage', 1)}x")
        print("=" * 70)

    # ─── 章节2：收益指标 ───

    def section_returns(self):
        s = self.s
        profit_abs = s.get("profit_total_abs", 0)
        profit_pct = s.get("profit_total", 0)
        cagr = s.get("cagr", 0)
        market_change = s.get("market_change", 0)
        alpha = profit_pct - market_change
        days = s.get("backtest_days", 1)

        print("\n【一、收益指标】")
        print(f"  累计收益率      : {pct(profit_pct)}  ({usd(profit_abs)})")
        print(f"  年化收益率(CAGR): {pct(cagr)}")
        print(f"  市场涨跌幅      : {pct(market_change)}  (白名单等权均值)")
        print(f"  超额收益(Alpha) : {pct(alpha)}")

        # 多空分拆
        long_abs = s.get("profit_total_long_abs", 0)
        short_abs = s.get("profit_total_short_abs", 0)
        print(f"  多头总盈亏      : {usd(long_abs)}")
        print(f"  空头总盈亏      : {usd(short_abs)}")

        # 日最佳/最差
        print(f"  单日最佳        : {pct(s.get('backtest_best_day', 0))}  ({usd(s.get('backtest_best_day_abs', 0))})")
        print(f"  单日最差        : {pct(s.get('backtest_worst_day', 0))}  ({usd(s.get('backtest_worst_day_abs', 0))})")
        print(f"  盈利天/平局天/亏损天: {s.get('winning_days')} / {s.get('draw_days')} / {s.get('losing_days')}")

    # ─── 章节3：风险指标 ───

    def section_risk(self):
        s = self.s
        mdd = s.get("max_drawdown_account", 0)
        mdd_abs = s.get("max_drawdown_abs", 0)
        dd_start = s.get("drawdown_start", "N/A")
        dd_end = s.get("drawdown_end", "N/A")
        dd_dur = s.get("drawdown_duration", "N/A")

        print("\n【二、风险指标】")
        print(f"  最大回撤(账户%) : {pct(mdd)}  ({usd(mdd_abs)})")
        print(f"  回撤起止        : {dd_start} ~ {dd_end}")
        print(f"  回撤持续时长    : {dd_dur}")
        print(f"  获利因子        : {round(s.get('profit_factor', 0), 4)}")

        trades = self.trades
        if trades:
            ratios = [t.get("profit_ratio", 0) for t in trades]
            absvals = [t.get("profit_abs", 0) for t in trades]
            print(f"  单笔最大盈      : {usd(max(absvals))}  ({pct(max(ratios))})")
            print(f"  单笔最大亏      : {usd(min(absvals))}  ({pct(min(ratios))})")
            big_loss = sum(1 for r in ratios if r < -0.05)
            print(f"  单笔浮亏>5%次数 : {big_loss} / {len(trades)} ({round(big_loss/len(trades)*100,1)})")

    # ─── 章节4：风险调整收益 ───

    def section_ratios(self):
        s = self.s
        sharpe = s.get("sharpe", 0)
        sortino = s.get("sortino", 0)
        calmar = s.get("calmar", 0)
        sqn = s.get("sqn", 0)
        mdd = s.get("max_drawdown_account", 1)
        cagr = s.get("cagr", 0)
        profit_pct = s.get("profit_total", 0)

        print("\n【三、风险调整收益】")
        print(f"  Sharpe Ratio    : {round(sharpe, 4)}  {self._rate_sharpe(sharpe)}")
        print(f"  Sortino Ratio   : {round(sortino, 4)}")
        print(f"  Calmar Ratio    : {round(calmar, 4)}  (年化/最大回撤)")
        print(f"  SQN (系统质量)  : {round(sqn, 4)}  {self._rate_sqn(sqn)}")
        if mdd > 0:
            ret_dd = round(profit_pct / mdd, 4)
            print(f"  收益回撤比      : {ret_dd}")

    def _rate_sharpe(self, v):
        if v < 0: return "❌ 负值"
        if v < 1: return "⚠ 差"
        if v < 2: return "△ 普通"
        if v < 3: return "✓ 良好"
        return "★ 优秀"

    def _rate_sqn(self, v):
        if v < 0: return "❌ 负值"
        if v < 1.6: return "⚠ 差"
        if v < 2.5: return "△ 普通"
        if v < 5: return "✓ 良好"
        return "★ 优秀(需验证)"

    # ─── 章节5：交易统计 ───

    def section_trade_stats(self):
        s = self.s
        total = s.get("total_trades", len(self.trades))
        wins = s.get("wins", 0)
        losses = s.get("losses", 0)
        winrate = s.get("winrate", 0)
        expectancy = s.get("expectancy", 0)
        expectancy_ratio = s.get("expectancy_ratio", 0)
        rejected = s.get("rejected_signals", 0)

        print("\n【四、交易统计】")
        print(f"  总交易笔数      : {total}  (日均 {s.get('trades_per_day', 0)} 笔)")
        print(f"  盈/亏/平        : {wins} / {losses} / {s.get('draws', 0)}")
        print(f"  交易胜率        : {pct(winrate)}")
        print(f"  期望值(USDT/笔) : {round(expectancy, 4)}")
        print(f"  期望值比率      : {round(expectancy_ratio, 6)}")
        print(f"  被拒绝信号      : {rejected}  (信号采纳率 {round(total/(total+rejected)*100,1) if (total+rejected)>0 else 'N/A'}%)")
        print(f"  最大连续盈      : {s.get('max_consecutive_wins', 0)} 笔")
        print(f"  最大连续亏      : {s.get('max_consecutive_losses', 0)} 笔")

        trades = self.trades
        if trades:
            w_abs = [t["profit_abs"] for t in trades if t.get("profit_abs", 0) > 0]
            l_abs = [abs(t["profit_abs"]) for t in trades if t.get("profit_abs", 0) < 0]
            if w_abs and l_abs:
                w_avg = sum(w_abs) / len(w_abs)
                l_avg = sum(l_abs) / len(l_abs)
                rr = round(w_avg / l_avg, 2)
                math_exp = winrate * w_avg - (1 - winrate) * l_avg
                print(f"  盈亏比(RR)      : {rr}  (盈均{usd(w_avg)} / 亏均{usd(l_avg)})")
                print(f"  数学期望(验证)  : {round(math_exp, 4)} USDT/笔")

        # 持仓时长
        print(f"  平均持仓时长    : {s.get('holding_avg', 'N/A')}")
        print(f"  盈利单均持仓    : {s.get('winner_holding_avg', 'N/A')}  (最长 {s.get('winner_holding_max', 'N/A')})")
        print(f"  亏损单均持仓    : {s.get('loser_holding_avg', 'N/A')}  (最长 {s.get('loser_holding_max', 'N/A')})")

    # ─── 章节6：仓位统计 ───

    def section_position(self):
        s = self.s
        long_c = s.get("trade_count_long", 0)
        short_c = s.get("trade_count_short", 0)
        total = long_c + short_c or 1

        print("\n【§06 仓位统计】")
        print(f"  多/空笔数       : {long_c}L / {short_c}S  ({round(long_c/total*100,1)}% / {round(short_c/total*100,1)}%)")
        print(f"  总成交量        : {usd(s.get('total_volume', 0))}")
        print(f"  均摊仓位        : {usd(s.get('avg_stake_amount', 0))}")

        # 最佳/最差品种
        bp = s.get("best_pair", {})
        wp = s.get("worst_pair", {})
        print(f"  最佳品种        : {bp.get('key', 'N/A')}  (共{bp.get('trades',0)}笔, 均收益{pct(bp.get('profit_mean',0))})")
        print(f"  最差品种        : {wp.get('key', 'N/A')}  (共{wp.get('trades',0)}笔, 均收益{pct(wp.get('profit_mean',0))})")

    # ─── §07 品种盈亏穿透（使用 results_per_pair） ───

    def section_by_pair(self):
        """使用 JSON 内置的 results_per_pair（含 TOTAL 汇总行）"""
        data = self.s.get("results_per_pair", [])
        if not data:
            return
        total_row = next((d for d in data if d.get("key") == "TOTAL"), None)
        pair_rows = [d for d in data if d.get("key") != "TOTAL"]
        pair_rows.sort(key=lambda x: x.get("profit_total_abs", 0), reverse=True)

        tot_pnl = total_row.get("profit_total_abs", 0) if total_row else sum(
            d.get("profit_total_abs", 0) for d in pair_rows)

        print("\n【§07 品种盈亏穿透 (results_per_pair)】")
        hdr = (f"  {'#':>3}  {'品种':<22} {'笔数':>5} {'胜率':>7} "
               f"{'总盈亏':>10} {'占比':>7} {'Sharpe':>8} {'期望值':>9} {'最大回撤%':>10}")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for i, item in enumerate(pair_rows, 1):
            pnl = item.get("profit_total_abs", 0)
            contrib = round(pnl / tot_pnl * 100, 1) if tot_pnl != 0 else 0
            flag = "✓" if pnl > 0 else "✗"
            print(
                f"  {i:>3}  {flag} {item['key']:<20} "
                f"{item.get('trades',0):>5} "
                f"{pct(item.get('winrate',0)):>7} "
                f"{round(pnl,2):>10} "
                f"{contrib:>6.1f}% "
                f"{round(item.get('sharpe',0),3):>8} "
                f"{round(item.get('expectancy',0),4):>9} "
                f"{pct(item.get('max_drawdown_account',0)):>10}"
            )
        if total_row:
            print("  " + "-" * (len(hdr) - 2))
            pnl = total_row.get("profit_total_abs", 0)
            print(
                f"  {'':>3}  {'★ TOTAL':<22} "
                f"{total_row.get('trades',0):>5} "
                f"{pct(total_row.get('winrate',0)):>7} "
                f"{round(pnl,2):>10} "
                f"{'100.0%':>7} "
                f"{round(total_row.get('sharpe',0),3):>8} "
                f"{round(total_row.get('expectancy',0),4):>9} "
                f"{pct(total_row.get('max_drawdown_account',0)):>10}"
            )

    # ─── §08 入场标签维度 ───

    def section_enter_tags(self):
        data = self.s.get("results_per_enter_tag", [])
        data_sorted = sorted(data, key=lambda x: x.get("profit_total_abs", 0), reverse=True)
        self._print_tag_table(data_sorted, "【§08 入场标签维度 (results_per_enter_tag)】", "入场标签")

    # ─── §09 出场原因维度 ───

    def section_exit_reasons(self):
        data = self.s.get("exit_reason_summary", [])
        data_sorted = sorted(data, key=lambda x: x.get("profit_total_abs", 0), reverse=True)
        self._print_tag_table(data_sorted, "【§09 出场原因维度 (exit_reason_summary)】", "出场原因")

    # ─── §10 混合标签维度 ───

    def section_mix_tags(self):
        data = self.s.get("mix_tag_stats", [])
        if not data:
            return
        data_sorted = sorted(data, key=lambda x: x.get("profit_total_abs", 0), reverse=True)
        self._print_tag_table(data_sorted, "【§10 混合标签维度 (mix_tag_stats，入场×出场组合)】", "入场 × 出场")

    # ─── §11 年度业绩分析 ───

    def section_yearly(self):
        """使用 periodic_breakdown.year 数据"""
        breakdown = self.s.get("periodic_breakdown", {})
        year_data = breakdown.get("year", [])

        print("\n【§11 年度业绩分析 (periodic_breakdown.year)】")
        if not year_data:
            print("  无数据")
            return
        print(f"  {'年份':>5} {'笔数':>6} {'总盈亏':>10} {'盈利因子':>9} {'盈/亏':>8} {'胜率':>7}  ASCII")
        print(f"  {'-'*58}")
        for item in sorted(year_data, key=lambda x: x.get("date_ts", 0)):
            date_str = item.get("date", "")
            year = date_str.split("/")[-1] if date_str else "?"
            pnl = item.get("profit_abs", 0)
            trades = item.get("trades", 0)
            wins = item.get("wins", 0)
            losses = item.get("losses", 0)
            pf = item.get("profit_factor", 0)
            wr = round(wins / trades * 100, 1) if trades > 0 else 0
            flag = "✓" if pnl > 0 else "✗"
            b = bar(pnl, scale=50)
            print(f"  {flag} {year:>4} {trades:>6} {round(pnl,2):>10} "
                  f"{round(pf,3):>9} {wins:>4}/{losses:<3} {wr:>6.1f}%  {b}")

    # ─── §12 月度盈亏全量 ───

    def section_monthly(self):
        """使用 periodic_breakdown.month 数据，按年分组"""
        breakdown = self.s.get("periodic_breakdown", {})
        month_data = breakdown.get("month", [])

        print("\n【§12 月度盈亏全量 (periodic_breakdown.month)】")
        if not month_data:
            print("  无数据")
            return

        # 按年分组
        from collections import defaultdict
        by_year = defaultdict(list)
        for item in month_data:
            date_str = item.get("date", "")
            parts = date_str.split("/")
            year = parts[-1] if len(parts) == 3 else "?"
            by_year[year].append(item)

        for year in sorted(by_year.keys()):
            print(f"\n  [{year}]  月份  {'盈亏':>9}  {'笔数':>5}  {'胜率':>6}  {'盈利因子':>8}")
            print(f"  {'':3}  {'-'*48}")
            for item in sorted(by_year[year], key=lambda x: x.get("date_ts", 0)):
                date_str = item.get("date", "")
                parts = date_str.split("/")
                month = parts[1] if len(parts) == 3 else "??"
                pnl = item.get("profit_abs", 0)
                trades = item.get("trades", 0)
                wins = item.get("wins", 0)
                pf = item.get("profit_factor", 0)
                wr = round(wins / trades * 100, 1) if trades > 0 else 0
                flag = "+" if pnl >= 0 else "-"
                print(f"  {flag}    {month}月  {round(pnl,2):>9}  {trades:>5}  {wr:>5.1f}%  {round(pf,3):>8}")

    # ─── §13 星期分布分析 ───

    def section_weekday(self):
        """使用 periodic_breakdown.weekday 数据"""
        breakdown = self.s.get("periodic_breakdown", {})
        wday_data = breakdown.get("weekday", [])

        print("\n【§13 星期分布分析 (periodic_breakdown.weekday)】")
        if not wday_data:
            print("  无数据")
            return

        WDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        print(f"  {'星期':>4} {'笔数':>6} {'总盈亏':>10} {'胜率':>7}  柱状图")
        print(f"  {'-'*52}")
        for item in sorted(wday_data, key=lambda x: x.get("date_ts", 0)):
            idx = item.get("date_ts", 0)
            try:
                wname = WDAY_NAMES[int(idx) % 7]
            except Exception:
                wname = str(idx)
            pnl = item.get("profit_abs", 0)
            trades = item.get("trades", 0)
            wins = item.get("wins", 0)
            wr = round(wins / trades * 100, 1) if trades > 0 else 0
            b = bar(pnl, scale=30)
            flag = "+" if pnl >= 0 else "-"
            print(f"  {wname}  {trades:>6} {round(pnl,2):>10} {wr:>6.1f}%  {flag}{b}")

    # ─── §14 回撤详情 ───

    def section_drawdown(self):
        s = self.s
        print("\n【§14 回撤详情】")
        print(f"  最大回撤(账户%) : {pct(s.get('max_drawdown_account', 0))}")
        print(f"  最大回撤绝对値  : {usd(s.get('max_drawdown_abs', 0))}")
        print(f"  回撤谷底资金    : {usd(s.get('csum_min', 0))}")
        print(f"  回撤峰値资金    : {usd(s.get('csum_max', 0))}")
        print(f"  回撤开始        : {s.get('drawdown_start', 'N/A')}")
        print(f"  回撤结束        : {s.get('drawdown_end', 'N/A')}")
        print(f"  回撤持续        : {s.get('drawdown_duration', 'N/A')}")

    # ─── §15 未平仓持仓 ───

    def section_left_open(self):
        data = self.s.get("left_open_trades", [])
        pair_rows = [d for d in data if d.get("key") != "TOTAL"]
        if not pair_rows:
            print("\n【§15 未平仓持仓】: 无未平仓持仓")
            return
        print(f"\n【§15 未平仓持仓 ({len(pair_rows)} 笔)】")
        print(f"  {'品种':<22} {'浮动盈亏':>10} {'持仓时长':>14}")
        for item in pair_rows:
            print(f"  {item.get('key','?'):<22} "
                  f"{round(item.get('profit_total_abs',0),2):>10} "
                  f"{item.get('duration_avg','N/A'):>14}")

    # ─── 章节12：策略参数 ───

    def section_strategy_params(self):
        s = self.s
        print("\n【十一、策略参数】")
        print(f"  止损            : {s.get('stoploss', 'N/A')}")
        print(f"  追踪止损        : {s.get('trailing_stop', False)}")
        print(f"  最小ROI         : {s.get('minimal_roi', {})}")
        print(f"  使用退出信号    : {s.get('use_exit_signal', False)}")
        print(f"  最大开仓数      : {s.get('max_open_trades_setting', 'N/A')}")
        print(f"  交易模式        : {s.get('trading_mode', 'N/A')} / {s.get('margin_mode', 'N/A')}")

    # ─── 章节13：综合诊断 ───

    def section_diagnosis(self):
        s = self.s
        sharpe = s.get("sharpe", 0)
        mdd = s.get("max_drawdown_account", 0)
        winrate = s.get("winrate", 0)
        cagr = s.get("cagr", 0)
        market_change = s.get("market_change", 0)
        days = s.get("backtest_days", 1)
        rejected = s.get("rejected_signals", 0)
        total = s.get("total_trades", 1)
        long_c = s.get("trade_count_long", 0)
        short_c = s.get("trade_count_short", 0)

        issues = []
        positives = []

        # 收益
        if cagr < 0:
            issues.append("🔴 年化收益为负，策略在该测试窗口无效")
        elif cagr < 0.2:
            issues.append("🟡 年化收益偏低(<20%)，扣除滑点后可能不足以跑赢通胀")
        else:
            positives.append(f"🟢 年化收益 {pct(cagr)}，具备盈利能力")

        # Alpha
        alpha = (1 + cagr) ** (days / 365) - 1 - market_change if days > 0 else 0
        if alpha < 0:
            issues.append(f"🔴 Alpha为负({pct(alpha)})，策略跑输简单持有白名单组合")
        else:
            positives.append(f"🟢 Alpha为正({pct(alpha)})，存在真实超额收益")

        # 回撤
        if mdd > 0.4:
            issues.append(f"🔴 最大回撤{pct(mdd)}超过40%，超出专业风控红线")
        elif mdd > 0.2:
            issues.append(f"🟡 最大回撤{pct(mdd)}在20-40%，需加强风控")
        else:
            positives.append(f"🟢 最大回撤{pct(mdd)}控制良好")

        # Sharpe
        if sharpe < 0:
            issues.append("🔴 Sharpe为负，风险收益严重失衡")
        elif sharpe < 1:
            issues.append(f"🟡 Sharpe={round(sharpe,2)}偏低，收益稳定性不足")
        elif sharpe >= 2:
            positives.append(f"🟢 Sharpe={round(sharpe,2)}，风险调整收益优秀")

        # 胜率/盈亏比
        trades = self.trades
        if trades:
            w_abs = [t["profit_abs"] for t in trades if t.get("profit_abs", 0) > 0]
            l_abs = [abs(t["profit_abs"]) for t in trades if t.get("profit_abs", 0) < 0]
            if w_abs and l_abs:
                w_avg = sum(w_abs) / len(w_abs)
                l_avg = sum(l_abs) / len(l_abs)
                rr = w_avg / l_avg
                breakeven_wr = 1 / (1 + rr) if rr > 0 else 1
                if winrate < breakeven_wr:
                    issues.append(f"🔴 胜率{pct(winrate)} < 盈亏平衡点{pct(breakeven_wr)}，数学期望为负")
                else:
                    positives.append(f"🟢 胜率{pct(winrate)} > 盈亏平衡点{pct(breakeven_wr)}，数学期望为正")

        # 方向
        if short_c == 0:
            issues.append("🔴 纯多头策略，无空头对冲，熊市风险敞口100%")
        elif long_c == 0:
            issues.append("🔴 纯空头策略，无多头对冲，牛市风险敞口100%")
        else:
            positives.append(f"🟢 双向交易(多{long_c}/空{short_c})，具备对冲能力")

        # 信号采纳率
        adopt_rate = total / (total + rejected) if (total + rejected) > 0 else 1
        if adopt_rate < 0.4:
            issues.append(f"🟡 信号采纳率仅{pct(adopt_rate)}，大量信号被仓位限制拒绝，实盘偏差风险高")

        # 回测窗口
        if days < 365:
            issues.append(f"🔴 回测窗口仅{days}天，样本量不足，结论不可靠")
        elif days < 730:
            issues.append(f"🟡 回测窗口{days}天，建议覆盖完整牛熊周期(>2年)")
        else:
            positives.append(f"🟢 回测窗口{days}天({round(days/365,1)}年)，样本量充足")

        print("\n【§17 综合诊断】")
        print()
        if positives:
            print("  ✅ 亮点:")
            for p in positives:
                print(f"     {p}")
        print()
        if issues:
            print("  ⚠ 风险/问题:")
            for i in issues:
                print(f"     {i}")
        print()

        # 简易评分
        score = 50
        score += min(max(cagr * 100, -20), 30)
        score += min(max((0.5 - mdd) * 60, -20), 20)
        score += min(max(sharpe * 10, -15), 15)
        score += 5 if short_c > 0 else -10
        score += 5 if days >= 730 else 0
        score = max(0, min(100, round(score)))
        print(f"  综合评分: {score} / 100")

    # ─── [可选] 交易明细列表 ───

    def section_trades_detail(self):
        if not self.trades:
            return
        print("\n【★ 交易明细列表 (--trades)】")
        hdr = (f"  {'#':>5}  {'品种':<22} {'方向':>4} {'入场时间':<20} "
               f"{'出场时间':<20} {'盈亏':>9} {'盈亏%':>8} {'出场原因':<22} 入场标签")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for i, t in enumerate(self.trades, 1):
            direction = "空" if t.get("is_short") else "多"
            pnl = round(t.get("profit_abs", 0), 2)
            pnl_pct = round(t.get("profit_ratio", 0) * 100, 2)
            flag = "+" if pnl >= 0 else ""
            print(
                f"  {i:>5}  {t.get('pair','?'):<22} {direction:>4} "
                f"{str(t.get('open_date','?'))[:19]:<20} "
                f"{str(t.get('close_date','?'))[:19]:<20} "
                f"{flag}{pnl:>8} {flag}{pnl_pct:>7}% "
                f"{str(t.get('exit_reason','?')):<22} "
                f"{t.get('enter_tag','?')}"
            )

    # ─── 主入口 ───

    def run(self):
        self.section_overview()
        self.section_returns()
        self.section_risk()
        self.section_ratios()
        self.section_trade_stats()
        self.section_position()
        self.section_by_pair()
        self.section_enter_tags()
        self.section_exit_reasons()
        self.section_mix_tags()
        self.section_yearly()
        self.section_monthly()
        self.section_weekday()
        self.section_drawdown()
        self.section_left_open()
        self.section_strategy_params()
        self.section_diagnosis()
        if self.show_trades:
            self.section_trades_detail()
        print("\n" + "=" * 70)
        print("  bt_parse.py 解析完成")
        print("=" * 70)


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

def find_latest_zip(base_dir="user_data/backtest_results"):
    p = Path(base_dir)
    zips = sorted(p.glob("backtest-result-*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not zips:
        raise FileNotFoundError(f"在 {base_dir} 中未找到回测结果文件")
    return str(zips[0])


if __name__ == "__main__":
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    pos_args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # --out <file>  直接写入 UTF-8 文件（绕过 PowerShell 重定向编码问题）
    out_file = None
    if "--out" in flags:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_file = sys.argv[idx + 1]
            flags = [f for f in flags if f != "--out"]
            pos_args = [a for a in pos_args if a != out_file]

    if pos_args:
        zip_path = pos_args[0]
    else:
        zip_path = find_latest_zip()
        print(f"[自动检测] 使用最新回测: {zip_path}\n")

    if out_file:
        import io
        buf = io.StringIO()
        _orig_stdout = sys.stdout
        sys.stdout = buf
        BacktestParser(zip_path).run()
        sys.stdout = _orig_stdout
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
        print(f"输出已写入: {out_file}")
    else:
        BacktestParser(zip_path).run()
