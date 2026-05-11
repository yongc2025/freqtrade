#!/usr/bin/env python3
"""
precompute_volume_ranking.py - 预计算每个时间点的动态选币排名

核心思路：
  由于 Freqtrade 回测的 pairlist 在数据加载之前就需要确定，
  所以我们把"动态选币"的逻辑完全移到离线预计算阶段。
  
  输出一个 JSON 文件，记录每个时间点应该交易哪些币种。
  然后用 VolumeRankingPairList 插件在回测时查表。

步骤：
  1. 下载所有潜在币种的历史数据
  2. 运行本脚本，生成 volume_ranking.json
  3. 回测时用 VolumeRankingPairList 读取该文件

速度影响：
  - 本脚本运行一次（离线，不影响回测速度）
  - 回测时 VolumeRankingPairList 直接查表，几乎零开销
  - 回测速度与 StaticPairList 几乎相同！
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def parse_timerange(timerange_str: str) -> tuple:
    if not timerange_str:
        return None, None
    parts = timerange_str.split("-")
    start = datetime.strptime(parts[0], "%Y%m%d") if parts[0] else None
    end = datetime.strptime(parts[1], "%Y%m%d") if len(parts) > 1 and parts[1] else None
    return start, end


def main():
    parser = argparse.ArgumentParser(
        description="预计算动态选币排名（生成 volume_ranking.json）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--datadir", required=True, help="Freqtrade 数据目录")
    parser.add_argument("--number-assets", type=int, default=40, help="top N 币种")
    parser.add_argument("--lookback-hours", type=int, default=1, help="成交量回看小时数 (实盘 VolumePairList lookback_days=0, 用 1h 近似)")
    parser.add_argument("--timerange", default="20250101-", help="时间范围")
    parser.add_argument("--output", default="volume_ranking.json", help="输出 JSON 文件")
    parser.add_argument("--timeframe", default="1h", help="数据时间框架")
    parser.add_argument("--step-hours", type=int, default=1, help="每隔几小时计算一次 (实盘 refresh_period=900s, 用 1h 近似)")
    parser.add_argument("--min-days-listed", type=int, default=30, help="最少上线天数 (匹配实盘 AgeFilter)")
    parser.add_argument("--pairlist-output", default="pair_universe.txt", help="币种超集列表输出")
    args = parser.parse_args()

    datadir = Path(args.datadir)
    if not datadir.exists():
        print(f"❌ 数据目录不存在: {datadir}")
        sys.exit(1)

    # 扫描可用数据
    print("扫描数据文件...")
    available_pairs = []
    # Freqtrade futures 数据格式: {PAIR}_USDT_USDT-1h-futures.feather
    for f in sorted(datadir.glob(f"*-{args.timeframe}-futures.feather")):
        pair_name = f.stem.replace(f"-{args.timeframe}-futures", "")
        # 0G_USDT_USDT -> 0G/USDT:USDT
        parts = pair_name.split("_")
        if len(parts) >= 3 and parts[-2] == "USDT" and parts[-1] == "USDT":
            base = "_".join(parts[:-2])
            pair_name = f"{base}/USDT:USDT"
        available_pairs.append(pair_name)

    if not available_pairs:
        for f in sorted(datadir.glob(f"*-{args.timeframe}.feather")):
            pair_name = f.stem.replace(f"-{args.timeframe}", "")
            pair_name = pair_name.replace("_", "/")
            if ":" not in pair_name:
                parts = pair_name.split("/")
                if len(parts) == 2:
                    pair_name = f"{parts[0]}/{parts[1]}:{parts[1]}"
            available_pairs.append(pair_name)

    if not available_pairs:
        for f in sorted(datadir.glob(f"*-{args.timeframe}-futures.json")):
            pair_name = f.stem.replace(f"-{args.timeframe}-futures", "")
            parts = pair_name.split("_")
            if len(parts) >= 3 and parts[-2] == "USDT" and parts[-1] == "USDT":
                base = "_".join(parts[:-2])
                pair_name = f"{base}/USDT:USDT"
            available_pairs.append(pair_name)

    print(f"找到 {len(available_pairs)} 个币种")

    # 加载所有数据
    print("加载历史数据...")
    all_data = {}
    for pair in available_pairs:
        # 0G/USDT:USDT -> 0G_USDT_USDT
        pair_filename = pair.replace("/", "_").replace(":", "_")
        # 尝试 futures 格式: {PAIR}_USDT_USDT-1h-futures.feather
        filepath = datadir / f"{pair_filename}-{args.timeframe}-futures.feather"
        if not filepath.exists():
            filepath = datadir / f"{pair_filename}-{args.timeframe}.feather"
        if not filepath.exists():
            filepath = datadir / f"{pair_filename}-{args.timeframe}-futures.json"
        if not filepath.exists():
            filepath = datadir / f"{pair_filename}-{args.timeframe}.json"
        if not filepath.exists():
            continue

        try:
            if filepath.suffix == ".feather":
                df = pd.read_feather(filepath)
            else:
                df = pd.read_json(filepath)
        except Exception:
            continue

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True, errors="coerce")
            df = df.set_index("date")

        if "close" in df.columns and "volume" in df.columns:
            # 计算 quoteVolume
            if "quote_volume" in df.columns:
                df["qv"] = df["quote_volume"]
            elif "quoteVolume" in df.columns:
                df["qv"] = df["quoteVolume"]
            else:
                df["qv"] = df["close"] * df["volume"]
            all_data[pair] = df

    print(f"成功加载 {len(all_data)} 个币种")

    # 过滤上线天数不足的币种（匹配实盘 AgeFilter）
    if args.min_days_listed > 0:
        min_candles = args.min_days_listed * 24  # 1h timeframe
        filtered = {}
        for pair, df in all_data.items():
            if len(df) >= min_candles:
                filtered[pair] = df
        skipped = len(all_data) - len(filtered)
        if skipped > 0:
            print(f"AgeFilter: 过滤掉 {skipped} 个上线不足 {args.min_days_listed} 天的币种")
        all_data = filtered
        print(f"AgeFilter 后剩余 {len(all_data)} 个币种")

    if len(all_data) < args.number_assets:
        print(f"⚠️  数据不足 {args.number_assets} 个币种，将使用全部 {len(all_data)} 个")

    # 构建统一时间轴
    all_ts = set()
    for df in all_data.values():
        all_ts.update(df.index.tolist())
    all_ts = sorted(all_ts)

    start_date, end_date = parse_timerange(args.timerange)
    if start_date:
        start_date = pd.Timestamp(start_date, tz="UTC")
        all_ts = [t for t in all_ts if t >= start_date]
    if end_date:
        end_date = pd.Timestamp(end_date, tz="UTC")
        all_ts = [t for t in all_ts if t <= end_date]

    print(f"时间范围: {all_ts[0]} ~ {all_ts[-1]}，共 {len(all_ts)} 根 K 线")

    # 按 step 筛选计算点
    step = pd.Timedelta(hours=args.step_hours)
    calc_times = [all_ts[0]]
    while calc_times[-1] + step <= all_ts[-1]:
        calc_times.append(calc_times[-1] + step)

    print(f"计算 {len(calc_times)} 个时间点的排名...")

    # ===== 核心优化：向量化计算 =====
    # 为每个币种构建 quoteVolume 的 Series（统一时间索引）
    unified_index = pd.DatetimeIndex(all_ts)
    qv_matrix = pd.DataFrame(index=unified_index)

    for pair, df in all_data.items():
        qv = df["qv"].reindex(unified_index).fillna(0)
        qv_matrix[pair] = qv

    # 滚动求和（向量化，一次性算完所有币种所有时间点）
    lookback = args.lookback_hours
    rolling_vol = qv_matrix.rolling(window=lookback, min_periods=1).sum()

    print("排名计算完成，开始生成结果...")

    # 对每个计算时间点取 top N
    ranking = {}
    all_selected = set()

    for t in calc_times:
        if t not in rolling_vol.index:
            continue
        row = rolling_vol.loc[t]
        # 排序取 top N
        top = row.nlargest(args.number_assets)
        top_pairs = [p for p in top.index if top[p] > 0]
        ts_key = str(int(t.timestamp()))
        ranking[ts_key] = top_pairs
        all_selected.update(top_pairs)

    # 输出
    output_path = Path(args.output)
    result = {
        "version": 1,
        "number_assets": args.number_assets,
        "lookback_hours": lookback,
        "timeframe": args.timeframe,
        "generated_at": datetime.now().isoformat(),
        "total_pairs": len(all_selected),
        "total_timestamps": len(ranking),
        "ranking": ranking,
    }

    with open(output_path, "w") as f:
        json.dump(result, f)

    print(f"✅ 排名数据已保存到: {output_path}")
    print(f"   {len(all_selected)} 个币种，{len(ranking)} 个时间点")
    print(f"   文件大小: {output_path.stat().st_size / 1024:.1f} KB")

    # 输出币种超集
    pair_output = Path(args.pairlist_output)
    with open(pair_output, "w") as f:
        for p in sorted(all_selected):
            f.write(f"{p}\n")

    print(f"✅ 币种超集已保存到: {pair_output}")

    # 统计
    freq = {}
    for pairs in ranking.values():
        for p in pairs:
            freq[p] = freq.get(p, 0) + 1

    top10 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\n📊 出现频率 top 10:")
    for p, c in top10:
        print(f"  {p}: {c}/{len(ranking)} ({c/len(ranking)*100:.1f}%)")

    print(f"\n📝 下一步：")
    print(f"  1. 将 {output_path} 放到 freqtrade 用户数据目录")
    print(f"  2. 使用 VolumeRankingPairList 插件进行回测")


if __name__ == "__main__":
    main()
