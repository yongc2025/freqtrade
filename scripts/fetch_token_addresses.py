"""
从 CoinGecko 拉取 Binance 期货代币的合约地址
生成 user_data/token_addresses.json 供策略使用

依赖: pip install requests
用法: python scripts/fetch_token_addresses.py

改进:
  - 增量缓存: 已抓取的地址存 cache 文件，下次运行跳过
  - 指数退避: 遇到 429 限流自动递增等待时间
  - 合理限速: 默认 6s 间隔适配 CoinGecko 免费 API (~10次/分钟)
"""

import json
import time
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    sys.exit(1)


COINGECKO_API = "https://api.coingecko.com/api/v3"
OUTPUT_PATH = Path(__file__).parent.parent / "user_data" / "token_addresses.json"
CACHE_PATH = Path(__file__).parent.parent / "user_data" / ".token_cache.json"

# 限速配置 (CoinGecko 免费 API: ~10-15 次/分钟)
REQUEST_INTERVAL = 6.0       # 每次请求间隔 (秒)
MAX_RETRIES = 5              # 最大重试次数
BASE_BACKOFF = 30            # 初始退避时间 (秒)
MAX_BACKOFF = 300            # 最大退避时间 (秒)


def load_cache() -> dict:
    """加载缓存"""
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    """保存缓存"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def api_get(url: str, params: dict = None, timeout: int = 15) -> requests.Response | None:
    """带指数退避的 API 请求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=timeout, params=params)
            if resp.status_code == 429:
                # 从响应头获取建议等待时间，否则用指数退避
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    wait = int(retry_after) + 5
                else:
                    wait = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                print(f"\n  ⏳ 限流! 等待 {wait}s (第{attempt+1}次重试)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                print(f"\n  ⚠️ 请求失败: {e}, 等待 {wait}s 重试...")
                time.sleep(wait)
            else:
                print(f"\n  ❌ 请求失败 (已重试{MAX_RETRIES}次): {e}")
                return None
    return None


def get_binance_futures_symbols() -> list[str]:
    """从 Binance 获取所有期货交易对的 symbol"""
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        symbols = set()
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                symbols.add(s["baseAsset"])
        return sorted(symbols)
    except Exception as e:
        print(f"获取 Binance 期货列表失败: {e}")
        return []


def get_coingecko_coins_list() -> list[dict]:
    """获取 CoinGecko 所有代币列表（包含平台地址）"""
    url = f"{COINGECKO_API}/coins/list"
    try:
        resp = api_get(url, params={"include_platform": "true"}, timeout=30)
        if resp:
            return resp.json()
        return []
    except Exception as e:
        print(f"获取 CoinGecko 代币列表失败: {e}")
        return []


def get_coingecko_coin_detail(coin_id: str) -> dict | None:
    """获取单个代币详情（包含各平台地址）"""
    url = f"{COINGECKO_API}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "false",
        "developer_data": "false",
    }
    resp = api_get(url, params=params)
    if resp:
        return resp.json()
    return None


def extract_addresses(detail: dict, platform_map: dict) -> dict:
    """从代币详情中提取地址"""
    platforms = detail.get("platforms", {})
    addresses = {}
    for cg_platform, chain_name in platform_map.items():
        addr = platforms.get(cg_platform, "")
        if addr and addr.strip():
            addresses[chain_name] = addr.strip()
    return addresses


def main():
    print("=" * 60)
    print("Binance 期货代币合约地址抓取工具 (v2)")
    print("=" * 60)

    platform_map = {
        "binance-smart-chain": "bsc",
        "ethereum": "eth",
        "solana": "sol",
    }

    # 加载缓存
    cache = load_cache()
    if cache:
        print(f"\n📦 已加载缓存: {len(cache)} 个代币")

    # Step 1: 获取 Binance 期货所有 symbol
    print("\n[1/3] 获取 Binance 期货代币列表...")
    binance_symbols = get_binance_futures_symbols()
    print(f"  共 {len(binance_symbols)} 个交易对")

    if not binance_symbols:
        print("无法获取 Binance 期货列表，退出")
        return

    # Step 2: 获取 CoinGecko 代币列表
    print("\n[2/3] 获取 CoinGecko 代币列表...")
    cg_coins = get_coingecko_coins_list()
    print(f"  共 {len(cg_coins)} 个代币")

    if not cg_coins:
        print("无法获取 CoinGecko 列表，退出")
        return

    # 建立 symbol → list of coin_id 映射
    symbol_to_coins: dict[str, list[dict]] = {}
    for coin in cg_coins:
        sym = coin.get("symbol", "").upper()
        if sym in binance_symbols:
            symbol_to_coins.setdefault(sym, []).append(coin)

    print(f"  匹配到 {len(symbol_to_coins)} 个 Binance 期货代币")

    # 先从 coins/list 的 platforms 字段尝试提取（免费，无额外请求）
    pre_filled = 0
    for symbol, coins in symbol_to_coins.items():
        if symbol in cache:
            continue
        for coin in coins:
            platforms = coin.get("platforms", {})
            addresses = {}
            for cg_platform, chain_name in platform_map.items():
                addr = platforms.get(cg_platform, "")
                if addr and addr.strip():
                    addresses[chain_name] = addr.strip()
            if addresses:
                cache[symbol] = addresses
                pre_filled += 1
                break

    if pre_filled:
        print(f"  ⚡ 从列表预填充 {pre_filled} 个代币地址 (无需额外请求)")
        save_cache(cache)

    # Step 3: 对缓存中没有的代币逐个获取详情
    need_fetch = {sym: coins for sym, coins in symbol_to_coins.items() if sym not in cache}
    print(f"\n[3/3] 获取合约地址 (需请求详情: {len(need_fetch)}/{len(symbol_to_coins)})...")

    if not need_fetch:
        print("  ✅ 所有代币已有缓存，无需请求!")
    else:
        total = len(need_fetch)
        fetched = 0
        skipped = 0
        failed = 0

        for i, (symbol, coins) in enumerate(need_fetch.items(), 1):
            print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)

            found = False
            request_failed = False
            for coin in coins:
                coin_id = coin["id"]
                detail = get_coingecko_coin_detail(coin_id)
                if not detail:
                    request_failed = True
                    continue

                addresses = extract_addresses(detail, platform_map)
                if addresses:
                    cache[symbol] = addresses
                    chains = ", ".join(addresses.keys())
                    print(f"✅ ({chains})")
                    found = True
                    fetched += 1
                    break

                # 限速
                time.sleep(REQUEST_INTERVAL)

            if not found:
                cache[symbol] = {}  # 标记为已查过（空地址）
                if request_failed:
                    print("❌ 请求失败")
                    failed += 1
                else:
                    print("⏭️ 无地址")
                    skipped += 1

            # 每处理 20 个保存一次缓存
            if i % 20 == 0:
                save_cache(cache)

            # 正常限速
            time.sleep(REQUEST_INTERVAL)

        save_cache(cache)
        print(f"\n  📊 详情请求结果: 成功 {fetched} | 跳过 {skipped} | 失败 {failed}")

    # 生成最终输出 (只包含有地址的)
    result = {k: v for k, v in cache.items() if v}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"✅ 完成! 共 {len(result)} 个代币有地址")
    print(f"📄 输出: {OUTPUT_PATH}")
    print(f"📦 缓存: {CACHE_PATH} ({len(cache)} 条)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
