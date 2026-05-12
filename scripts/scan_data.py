#!/usr/bin/env python3
"""
扫描本地 Freqtrade 数据目录，报告每个交易对的数据范围。
用法: python3 scan_data.py [datadir] [timeframe] [trading_mode]

默认: user_data/data/binance  1h  futures

输出同时写入终端和日志文件: user_data/logs/scan_data_YYYYMMDD_HHMMSS.log
"""

import sys
import os
from pathlib import Path
from datetime import datetime, UTC

# 添加 freqtrade 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Tee:
    """同时输出到终端和文件"""
    def __init__(self, filepath):
        self.file = open(filepath, "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.stdout.flush()
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()
        sys.stdout = self.stdout


def scan(datadir: str = "user_data/data/binance", timeframe: str = "1h", mode: str = "futures"):
    datadir = Path(datadir)

    # 设置日志输出
    log_dir = Path(__file__).resolve().parent.parent / "user_data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"scan_data_{timestamp}.log"
    tee = Tee(log_path)
    sys.stdout = tee
    print(f"日志文件: {log_path}\n")

    from freqtrade.data.history.datahandlers import get_datahandler
    from freqtrade.enums import CandleType, TradingMode

    trading_mode = TradingMode(mode)
    candle_type = CandleType.FUTURES if mode == "futures" else CandleType.SPOT

    # 自动检测数据格式
    data_format = "feather"
    for fmt in ["feather", "json", "hdf5"]:
        test_dir = datadir / ("futures" if mode == "futures" else "")
        if test_dir.exists() and list(test_dir.glob(f"*.{fmt}")):
            data_format = fmt
            break

    print(f"数据目录: {datadir}")
    print(f"时间框架: {timeframe}")
    print(f"交易模式: {mode}")
    print(f"数据格式: {data_format}")
    print("=" * 80)

    handler = get_datahandler(datadir, data_format)
    all_pairs = handler.ohlcv_get_pairs(datadir, timeframe, candle_type)

    if not all_pairs:
        print("未找到任何数据文件！")
        print(f"请检查目录是否存在: {datadir / ('futures' if mode == 'futures' else '')}")
        tee.close()
        return

    print(f"\n共找到 {len(all_pairs)} 个交易对\n")

    # 收集信息
    results = []
    for pair in sorted(all_pairs):
        try:
            first, last, length = handler.ohlcv_data_min_max(pair, timeframe, candle_type)
            results.append((pair, first, last, length))
        except Exception as e:
            results.append((pair, None, None, 0))

    # 按起始日期排序
    results.sort(key=lambda x: x[1] if x[1] else datetime.max)

    # 统计
    target_start = datetime(2024, 1, 1, tzinfo=UTC)
    full_coverage = 0
    partial_coverage = 0
    no_data = 0

    print(f"{'交易对':<30} {'起始日期':<22} {'结束日期':<22} {'数据条数':>8}  {'状态'}")
    print("-" * 100)

    for pair, first, last, length in results:
        if first is None:
            status = "❌ 无数据"
            no_data += 1
            print(f"{pair:<30} {'N/A':<22} {'N/A':<22} {0:>8}  {status}")
            continue

        first_str = first.strftime("%Y-%m-%d %H:%M")
        last_str = last.strftime("%Y-%m-%d %H:%M")

        if first <= target_start:
            status = "✅ 完整"
            full_coverage += 1
        else:
            days_missing = (first - target_start).days
            status = f"⚠️  缺少 {days_missing} 天"
            partial_coverage += 1

        print(f"{pair:<30} {first_str:<22} {last_str:<22} {length:>8}  {status}")

    # 汇总
    print("\n" + "=" * 100)
    print(f"汇总:")
    print(f"  总交易对数:     {len(results)}")
    print(f"  ✅ 完整覆盖:    {full_coverage} (从 2024-01-01 或更早开始)")
    print(f"  ⚠️  部分覆盖:    {partial_coverage} (晚于 2024-01-01 开始)")
    print(f"  ❌ 无数据:       {no_data}")

    if partial_coverage > 0:
        print(f"\n部分覆盖的交易对 (晚于 2024-01-01 上线):")
        for pair, first, last, length in results:
            if first and first > target_start:
                print(f"  {pair}: 从 {first.strftime('%Y-%m-%d')} 开始")

    # 最早和最晚的币
    valid = [(p, f, l, n) for p, f, l, n in results if f is not None]
    if valid:
        earliest = min(valid, key=lambda x: x[1])
        latest = max(valid, key=lambda x: x[2])
        print(f"\n最早有数据: {earliest[0]} ({earliest[1].strftime('%Y-%m-%d')})")
        print(f"最晚有数据: {latest[0]} ({latest[2].strftime('%Y-%m-%d')})")

    print(f"\n{'=' * 100}")
    print(f"完整日志已保存到: {log_path}")
    tee.close()


if __name__ == "__main__":
    datadir = sys.argv[1] if len(sys.argv) > 1 else "user_data/data/binance"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"
    mode = sys.argv[3] if len(sys.argv) > 3 else "futures"
    scan(datadir, timeframe, mode)
