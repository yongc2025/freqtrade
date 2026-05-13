"""
Binance 合约历史数据下载器

下载资金费率、持仓量(OI)、大户多空比、Taker买卖比，
保存为 CSV 文件供策略回测使用。

用法：
    python user_data/scripts/download_contract_data.py [--days 30] [--pairs DOGE,LINK,SOL]

数据来源：Binance Futures API（无需 API Key，公开接口）
"""

import argparse
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import ccxt
import pandas as pd


def create_exchange():
    """创建 Binance 期货交易所实例"""
    return ccxt.binance({
        "options": {"defaultType": "future"},
        "timeout": 30000,
    })


def download_funding_rate(exchange, symbol: str, days: int) -> pd.DataFrame:
    """下载资金费率历史"""
    bsymbol = symbol.replace("/", "").replace(":USDT", "")
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    while True:
        try:
            resp = exchange.fapiPublicGetFundingRate({
                "symbol": bsymbol,
                "startTime": since,
                "limit": 1000,
            })
        except Exception as e:
            print(f"  ⚠ 资金费率下载失败 {symbol}: {e}")
            break

        if not resp:
            break

        all_data.extend(resp)
        last_time = int(resp[-1]["fundingTime"])
        if len(resp) < 1000:
            break
        since = last_time + 1
        time.sleep(0.1)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["funding_rate"] = df["fundingRate"].astype(float)
    df = df[["timestamp", "funding_rate"]].sort_values("timestamp").reset_index(drop=True)
    return df


def download_oi_history(exchange, symbol: str, days: int) -> pd.DataFrame:
    """下载持仓量历史（5min 粒度）"""
    bsymbol = symbol.replace("/", "").replace(":USDT", "")
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    while True:
        try:
            resp = exchange.fapiPublicGetOpenInterestHist({
                "symbol": bsymbol,
                "period": "5m",
                "startTime": since,
                "limit": 500,
            })
        except Exception as e:
            print(f"  ⚠ OI 下载失败 {symbol}: {e}")
            break

        if not resp:
            break

        all_data.extend(resp)
        last_time = int(resp[-1]["timestamp"])
        if len(resp) < 500:
            break
        since = last_time + 1
        time.sleep(0.1)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["oi"] = df["sumOpenInterest"].astype(float)
    df["oi_value"] = df["sumOpenInterestValue"].astype(float)
    df = df[["timestamp", "oi", "oi_value"]].sort_values("timestamp").reset_index(drop=True)
    return df


def download_top_ls_ratio(exchange, symbol: str, days: int) -> pd.DataFrame:
    """下载大户多空比（持仓量）"""
    bsymbol = symbol.replace("/", "").replace(":USDT", "")
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    while True:
        try:
            resp = exchange.fapiPublicGetTopLongShortPositionRatio({
                "symbol": bsymbol,
                "period": "5m",
                "startTime": since,
                "limit": 500,
            })
        except Exception as e:
            print(f"  ⚠ 多空比下载失败 {symbol}: {e}")
            break

        if not resp:
            break

        all_data.extend(resp)
        last_time = int(resp[-1]["timestamp"])
        if len(resp) < 500:
            break
        since = last_time + 1
        time.sleep(0.1)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["top_ls_ratio"] = df["longShortRatio"].astype(float)
    df = df[["timestamp", "top_ls_ratio"]].sort_values("timestamp").reset_index(drop=True)
    return df


def download_taker_ratio(exchange, symbol: str, days: int) -> pd.DataFrame:
    """下载 Taker 买卖比"""
    bsymbol = symbol.replace("/", "").replace(":USDT", "")
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    while True:
        try:
            resp = exchange.fapiPublicGetTakerlongshortRatio({
                "symbol": bsymbol,
                "period": "5m",
                "startTime": since,
                "limit": 500,
            })
        except Exception as e:
            print(f"  ⚠ Taker 比下载失败 {symbol}: {e}")
            break

        if not resp:
            break

        all_data.extend(resp)
        last_time = int(resp[-1]["timestamp"])
        if len(resp) < 500:
            break
        since = last_time + 1
        time.sleep(0.1)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["taker_ls_ratio"] = df["buySellRatio"].astype(float)
    df = df[["timestamp", "taker_ls_ratio"]].sort_values("timestamp").reset_index(drop=True)
    return df


def merge_contract_data(
    funding_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    ls_df: pd.DataFrame,
    taker_df: pd.DataFrame,
) -> pd.DataFrame:
    """合并所有合约数据，按 5min 对齐"""
    dfs = []

    if not funding_df.empty:
        # 资金费率每 8h 一次，向前填充到 5min
        funding_df = funding_df.set_index("timestamp").resample("5min").ffill().reset_index()
        dfs.append(funding_df)

    if not oi_df.empty:
        dfs.append(oi_df)

    if not ls_df.empty:
        dfs.append(ls_df.set_index("timestamp"))

    if not taker_df.empty:
        dfs.append(taker_df.set_index("timestamp"))

    if not dfs:
        return pd.DataFrame()

    # 合并
    result = dfs[0]
    if isinstance(result.index, pd.DatetimeIndex):
        result = result.reset_index()

    for df in dfs[1:]:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        result = pd.merge_asof(
            result.sort_values("timestamp"),
            df.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta("10min"),
        )

    # 填充缺失值
    result = result.ffill().bfill()

    return result


def download_pair(exchange, symbol: str, days: int, output_dir: Path) -> bool:
    """下载单个交易对的全部合约数据"""
    pair_name = symbol.replace("/", "_").replace(":", "_")
    output_file = output_dir / f"{pair_name}_contract.csv"

    print(f"\n📥 {symbol}...")

    # 下载各类数据
    print("  ├─ 资金费率...", end=" ", flush=True)
    funding_df = download_funding_rate(exchange, symbol, days)
    print(f"{len(funding_df)} 条")

    print("  ├─ 持仓量...", end=" ", flush=True)
    oi_df = download_oi_history(exchange, symbol, days)
    print(f"{len(oi_df)} 条")

    print("  ├─ 大户多空比...", end=" ", flush=True)
    ls_df = download_top_ls_ratio(exchange, symbol, days)
    print(f"{len(ls_df)} 条")

    print("  └─ Taker买卖比...", end=" ", flush=True)
    taker_df = download_taker_ratio(exchange, symbol, days)
    print(f"{len(taker_df)} 条")

    # 合并
    merged = merge_contract_data(funding_df, oi_df, ls_df, taker_df)

    if merged.empty:
        print(f"  ⚠ {symbol} 无数据，跳过")
        return False

    # 保存
    merged.to_csv(output_file, index=False)
    print(f"  ✅ 保存到 {output_file} ({len(merged)} 行)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Binance 合约历史数据下载器")
    parser.add_argument("--days", type=int, default=30, help="下载天数（默认30，Binance最多保留30天）")
    parser.add_argument("--pairs", type=str, default="", help="交易对列表，逗号分隔（默认下载 VolumePairList 前20）")
    parser.add_argument("--output", type=str, default="user_data/data/contract", help="输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("Binance 合约历史数据下载器")
    print("=" * 50)
    print(f"天数: {args.days}")
    print(f"输出: {output_dir}")

    exchange = create_exchange()

    # 确定交易对
    if args.pairs:
        symbols = [p.strip() for p in args.pairs.split(",")]
        # 自动补全格式
        symbols = [
            s if "/" in s else f"{s}/USDT:USDT"
            for s in symbols
        ]
    else:
        # 默认下载成交量前 20 的 USDT 永续合约
        print("\n获取成交量排名...")
        tickers = exchange.fetch_tickers()
        usdt_futures = [
            t for t in tickers
            if t.endswith(":USDT") and "/USDT" in t
        ]
        # 按成交额排序
        usdt_futures.sort(
            key=lambda t: tickers[t].get("quoteVolume", 0) or 0,
            reverse=True,
        )
        # 排除稳定币和反向代币
        skip = {"BUSD", "USDC", "TUSD", "DAI", "USDP", "FDUSD"}
        symbols = []
        for s in usdt_futures:
            base = s.split("/")[0]
            if base in skip:
                continue
            if any(x in base for x in ["BEAR", "BULL", "UP", "DOWN", "HEDGE"]):
                continue
            symbols.append(s)
            if len(symbols) >= 20:
                break

    print(f"\n交易对 ({len(symbols)}):")
    for s in symbols:
        print(f"  - {s}")

    # 逐个下载
    success = 0
    for symbol in symbols:
        try:
            if download_pair(exchange, symbol, args.days, output_dir):
                success += 1
        except Exception as e:
            print(f"  ❌ {symbol} 下载异常: {e}")
        time.sleep(0.5)  # 避免限频

    print(f"\n{'=' * 50}")
    print(f"✅ 完成: {success}/{len(symbols)} 个交易对下载成功")
    print(f"📁 数据目录: {output_dir}")


if __name__ == "__main__":
    main()
