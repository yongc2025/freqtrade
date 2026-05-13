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
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json as _json

import ccxt
import pandas as pd


# ── 限流器 ──────────────────────────────────────────────────
class RateLimiter:
    """
    Binance fapi 限流控制器
    - 全局最小请求间隔
    - 429 指数退避重试
    - 解析 X-MBX-USED-WEIGHT 响应头动态调速
    """

    def __init__(self, min_interval: float = 0.2, max_weight_ratio: float = 0.7):
        self.min_interval = min_interval          # 最小请求间隔(秒)
        self.max_weight_ratio = max_weight_ratio   # 已用权重占比阈值(超过则暂停)
        self.last_request_time = 0.0
        self.used_weight = 0
        self.weight_limit = 2400                   # Binance 默认每分钟上限

    def wait(self):
        """请求前等待，确保最小间隔"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def update_from_response(self, headers):
        """从响应头更新权重使用情况"""
        if headers is None:
            return
        # 支持 dict 和 http.client.HTTPMessage
        used = None
        limit = None
        for key in ("X-MBX-USED-WEIGHT-1M", "x-mbx-used-weight-1m", "X-MBX-USED-WEIGHT", "x-mbx-used-weight"):
            val = headers.get(key) if hasattr(headers, 'get') else None
            if val is not None:
                try:
                    used = int(val)
                    break
                except ValueError:
                    pass
        for key in ("X-MBX-ORDER-COUNT-1M", "x-mbx-order-count-1m"):
            pass  # 仅关注 weight

        if used is not None:
            self.used_weight = used

        # 如果已用权重超过阈值，主动暂停
        if self.used_weight > self.weight_limit * self.max_weight_ratio:
            wait_time = max(5.0, 60.0 - (time.time() - self.last_request_time))
            print(f"  ⏳ 已用权重 {self.used_weight}/{self.weight_limit}，暂停 {wait_time:.0f}s...")
            time.sleep(wait_time)

    def on_success(self):
        self.last_request_time = time.time()

    def on_429(self, retry_count: int) -> float:
        """429 限流回调，返回建议等待时间（指数退避）"""
        wait = min(60.0, (2 ** retry_count) * 2.0)  # 2s, 4s, 8s, 16s, 32s, 60s
        print(f"  ⚠ 触发限频(429)，等待 {wait:.0f}s 后重试...")
        return wait


_rate_limiter = RateLimiter(min_interval=0.25)


def create_exchange(config_path: str | None = None):
    """创建 Binance 期货交易所实例，自动读取 config 中的代理配置"""
    ccxt_config = {
        "options": {"defaultType": "future"},
        "timeout": 30000,
    }

    # 从 freqtrade config 读取代理
    if config_path:
        try:
            import json
            with open(config_path, "r") as f:
                config = json.load(f)

            for key in ("ccxt_config", "ccxt_async_config"):
                cfg = config.get("exchange", {}).get(key, {})
                # ccxt_config.proxies 格式
                if "proxies" in cfg:
                    proxy = cfg["proxies"].get("https") or cfg["proxies"].get("http")
                    if proxy:
                        ccxt_config["proxies"] = cfg["proxies"]
                        print(f"🔧 代理: {proxy}")
                        break
                # ccxt_async_config.aiohttp_proxy 格式
                if "aiohttp_proxy" in cfg:
                    proxy = cfg["aiohttp_proxy"]
                    ccxt_config["proxies"] = {"http": proxy, "https": proxy}
                    print(f"🔧 代理: {proxy}")
                    break
        except Exception as e:
            print(f"⚠ 读取代理配置失败: {e}")

    exchange = ccxt.binance(ccxt_config)
    # 加载市场数据，确保隐式 API 方法可用
    exchange.load_markets()
    return exchange


def _call_fapi(exchange, method_name: str, params: dict, max_retries: int = 3):
    """
    兼容不同 ccxt 版本调用 Binance fapi 隐式 API。

    ccxt 4.x 方法名映射：
      - 资金费率: fapiPublicGetFundingRate        (fapiPublic)
      - 持仓量:   fapiDataGetOpenInterestHist      (fapiData, 非 fapiPublic!)
      - 多空比:   fapiDataGetTopLongShortPositionRatio (fapiData)
      - Taker比:  fapiDataGetTakerlongshortRatio   (fapiData)

    自动尝试 fapiPublic -> fapiData -> 直接HTTP 兜底。
    内置限流、429重试、权重监控。
    """
    # 1. 直接调用
    method = getattr(exchange, method_name, None)
    if callable(method):
        return _call_with_retry(method, params, max_retries)

    # 2. fapiPublic <-> fapiData 互换尝试
    alt_names = []
    if "fapiPublicGet" in method_name:
        alt_names.append(method_name.replace("fapiPublicGet", "fapiDataGet"))
        alt_names.append(method_name.replace("fapiPublicGet", "fapiDataGet").lower())
    elif "fapiDataGet" in method_name:
        alt_names.append(method_name.replace("fapiDataGet", "fapiPublicGet"))
        alt_names.append(method_name.replace("fapiDataGet", "fapiPublicGet").lower())

    for alt_name in alt_names:
        method = getattr(exchange, alt_name, None)
        if callable(method):
            return _call_with_retry(method, params, max_retries)

    # 3. 直接 HTTP 请求（兜底，不依赖 ccxt 隐式 API）
    path_map = {
        "fapiPublicGetFundingRate": "/fapi/v1/fundingRate",
        "fapiDataGetOpenInterestHist": "/futures/data/openInterestHist",
        "fapiPublicGetOpenInterestHist": "/futures/data/openInterestHist",
        "fapiDataGetTopLongShortPositionRatio": "/futures/data/top-long-short-position-ratio",
        "fapiPublicGetTopLongShortPositionRatio": "/futures/data/top-long-short-position-ratio",
        "fapiDataGetTakerlongshortRatio": "/futures/data/takerlongshortRatio",
        "fapiPublicGetTakerlongshortRatio": "/futures/data/takerlongshortRatio",
    }
    path = path_map.get(method_name)
    if path:
        return _http_get_with_retry(f"https://fapi.binance.com{path}", params, max_retries)

    raise AttributeError(f"无法找到方法 {method_name}，请升级 ccxt: pip install ccxt --upgrade")


def _call_with_retry(method, params: dict, max_retries: int):
    """带限流和重试的 ccxt 隐式 API 调用"""
    for attempt in range(max_retries + 1):
        _rate_limiter.wait()
        try:
            result = method(params)
            _rate_limiter.on_success()
            return result
        except ccxt.RateLimitExceeded as e:
            wait = _rate_limiter.on_429(attempt)
            time.sleep(wait)
        except ccxt.NetworkError as e:
            if attempt < max_retries:
                time.sleep(2.0)
            else:
                raise
    raise RuntimeError(f"超过最大重试次数 ({max_retries})")


def _http_get_with_retry(base_url: str, params: dict, max_retries: int):
    """带限流和重试的直接 HTTP 请求"""
    query = urlencode(params)
    full_url = f"{base_url}?{query}"

    for attempt in range(max_retries + 1):
        _rate_limiter.wait()
        try:
            req = Request(full_url)
            req.add_header("User-Agent", "freqtrade-contract-downloader/1.0")
            with urlopen(req, timeout=30) as resp:
                _rate_limiter.on_success()
                # 读取响应头更新权重
                _rate_limiter.update_from_response(resp.headers)
                return _json.loads(resp.read())
        except HTTPError as e:
            if e.code == 429:
                # 解析 Retry-After 头
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    wait = float(retry_after)
                else:
                    wait = _rate_limiter.on_429(attempt)
                time.sleep(wait)
            elif e.code == 418:
                # IP 被封，等待更久
                print(f"  ❌ IP 被 Binance 封禁(418)，等待 120s...")
                time.sleep(120)
            else:
                raise RuntimeError(f"Binance API 错误 {e.code}: {e.reason}")
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2.0)
            else:
                raise RuntimeError(f"直接请求 Binance API 失败: {e}")

    raise RuntimeError(f"超过最大重试次数 ({max_retries})")


def _call_fapi_with_fallback(exchange, method_name: str, params: dict, max_retries: int = 3):
    """
    带 startTime 降级的 fapi 调用。
    某些 fapiData 接口对 startTime 格式敏感（新币上市时间不足），
    失败时自动去掉 startTime 重试（取最近数据）。
    """
    try:
        return _call_fapi(exchange, method_name, params, max_retries)
    except Exception as e:
        err_str = str(e)
        if "startTime" in err_str or "-1130" in err_str:
            fallback = {k: v for k, v in params.items() if k != "startTime"}
            return _call_fapi(exchange, method_name, fallback, max_retries)
        raise


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
        pass  # 限流器统一控制间隔

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
            resp = _call_fapi_with_fallback(exchange, "fapiPublicGetOpenInterestHist", {
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
        pass  # 限流器统一控制间隔

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
            resp = _call_fapi_with_fallback(exchange, "fapiPublicGetTopLongShortPositionRatio", {
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
        pass  # 限流器统一控制间隔

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
            resp = _call_fapi_with_fallback(exchange, "fapiPublicGetTakerlongshortRatio", {
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
        pass  # 限流器统一控制间隔

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

    exchange = create_exchange(config_path=args.config)

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
        time.sleep(1.0)  # 交易对间隔，配合限流器

    print(f"\n{'=' * 50}")
    print(f"✅ 完成: {success}/{len(symbols)} 个交易对下载成功")
    print(f"📁 数据目录: {output_dir}")


if __name__ == "__main__":
    main()
