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
    exchange = ccxt.binance({
        "options": {"defaultType": "future"},
        "timeout": 30000,
    })
    # 加载市场数据，确保隐式 API 方法可用
    exchange.load_markets()
    return exchange


def _call_fapi(exchange, method_name: str, params: dict):
    """
    兼容不同 ccxt 版本调用 Binance fapi 隐式 API。
    按优先级尝试多种方式：
      1. 直接调用隐式方法
      2. 常见命名变体
      3. 通过 ccxt 的 fetch 方法
      4. 直接 HTTP 请求（兜底）
    """
    import re
    from urllib.parse import urlencode
    from urllib.request import urlopen
    import json as _json

    # 1. 尝试直接调用
    method = getattr(exchange, method_name, None)
    if callable(method):
        return method(params)

    # 2. 尝试常见变体
    suffix = method_name.replace("fapiPublicGet", "")
    variants = [
        # 原样
        f"fapiPublicGet{suffix}",
        # 全小写后缀
        f"fapiPublicGet{suffix.lower()}",
        # 每段首字母大写其余小写
        f"fapiPublicGet{''.join(p[0].upper() + p[1:].lower() if p else '' for p in re.split(r'([A-Z][a-z]*)', suffix) if p)}",
    ]
    for variant in variants:
        method = getattr(exchange, variant, None)
        if callable(method):
            return method(params)

    # 3. 尝试 ccxt 的通用 fetch
    path_map = {
        "fapiPublicGetOpenInterestHist": "/fapi/v1/openInterestHist",
        "fapiPublicGetTopLongShortPositionRatio": "/futures/data/top-long-short-position-ratio",
        "fapiPublicGetTakerlongshortRatio": "/futures/data/takerlongshortRatio",
        "fapiPublicGetFundingRate": "/fapi/v1/fundingRate",
    }
    path = path_map.get(method_name)
    if path:
        # 尝试 ccxt 内置 fetch（新版支持）
        try:
            url = exchange.urls["fapiPublic"] + path + "?" + urlencode(params)
            return exchange.fetch(url)
        except (KeyError, TypeError):
            pass

        # 4. 直接 HTTP 请求（兜底方案，不依赖 ccxt 隐式 API）
        base_url = "https://fapi.binance.com"
        query = urlencode(params)
        full_url = f"{base_url}{path}?{query}"
        try:
            with urlopen(full_url, timeout=30) as resp:
                return _json.loads(resp.read())
        except Exception as e:
            raise RuntimeError(f"直接请求 Binance API 失败: {e}")

    raise AttributeError(f"无法找到方法 {method_name}，请升级 ccxt: pip install ccxt --upgrade")


def download_funding_rate(exchange, symbol: str, days: int) -> pd.DataFrame:
    """下载资金费率历史"""
    bsymbol = symbol.replace("/", "").replace(":USDT", "")
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    all_data = []
    while True:
        try:
            resp = _call_fapi(exchange, "fapiPublicGetFundingRate", {
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
            resp = _call_fapi(exchange, "fapiPublicGetOpenInterestHist", {
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
            resp = _call_fapi(exchange, "fapiPublicGetTopLongShortPositionRatio", {
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
            resp = _call_fapi(exchange, "fapiPublicGetTakerlongshortRatio", {
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


def load_pairs_from_config(config_path: str) -> list[str]:
    """从 freqtrade config 文件读取交易对列表"""
    import json

    with open(config_path, "r") as f:
        config = json.load(f)

    # 优先用 pair_whitelist
    whitelist = config.get("exchange", {}).get("pair_whitelist", [])
    if whitelist:
        return whitelist

    # pair_whitelist 为空，从 pairlist 推断（VolumePairList 等动态 pairlist 无法直接读取）
    print("⚠ pair_whitelist 为空（使用了动态 pairlist），请用 --pairs 指定或用 --config 配合 VolumePairList")
    return []


def main():
    parser = argparse.ArgumentParser(description="Binance 合约历史数据下载器")
    parser.add_argument("--days", type=int, default=30, help="下载天数（默认30，Binance最多保留30天）")
    parser.add_argument("--pairs", type=str, default="", help="交易对列表，逗号分隔（优先级高于 --config）")
    parser.add_argument("--config", type=str, default="user_data/config_binance_futures.json", help="freqtrade 配置文件路径")
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
        symbols = [
            s if "/" in s else f"{s}/USDT:USDT"
            for s in symbols
        ]
    else:
        symbols = load_pairs_from_config(args.config)
        if not symbols:
            # 回退：下载成交量前 20
            print("\n从 config 未获取到交易对，使用成交量前 20...")
            tickers = exchange.fetch_tickers()
            usdt_futures = [
                t for t in tickers
                if t.endswith(":USDT") and "/USDT" in t
            ]
            usdt_futures.sort(
                key=lambda t: tickers[t].get("quoteVolume", 0) or 0,
                reverse=True,
            )
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
    if args.pairs:
        print(f"  来源: --pairs 参数")
    elif symbols:
        print(f"  来源: {args.config}")
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
