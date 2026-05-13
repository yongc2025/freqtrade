"""
从 CoinGecko 拉取 Binance 期货代币的合约地址
生成 user_data/token_addresses.json 供策略使用

依赖: pip install requests
用法: python user_data/scripts/fetch_token_addresses.py
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
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取 CoinGecko 代币列表失败: {e}")
        return []


def get_coingecko_coin_detail(coin_id: str) -> dict | None:
    """获取单个代币详情（包含各平台地址）"""
    url = f"{COINGECKO_API}/coins/{coin_id}"
    try:
        resp = requests.get(url, timeout=15, params={"localization": "false", "tickers": "false", "market_data": "false"})
        if resp.status_code == 429:
            print(f"  Rate limited, waiting 60s...")
            time.sleep(60)
            resp = requests.get(url, timeout=15, params={"localization": "false", "tickers": "false", "market_data": "false"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  获取 {coin_id} 详情失败: {e}")
        return None


def main():
    print("=" * 60)
    print("Binance 期货代币合约地址抓取工具")
    print("=" * 60)

    # Step 1: 获取 Binance 期货所有 symbol
    print("\n[1/3] 获取 Binance 期货代币列表...")
    binance_symbols = get_binance_futures_symbols()
    print(f"  共 {len(binance_symbols)} 个交易对")

    if not binance_symbols:
        print("无法获取 Binance 期货列表，退出")
        return

    # Step 2: 获取 CoinGecko 代币列表，建立 symbol → coin_id 映射
    print("\n[2/3] 获取 CoinGecko 代币列表...")
    cg_coins = get_coingecko_coins_list()
    print(f"  共 {len(cg_coins)} 个代币")

    if not cg_coins:
        print("无法获取 CoinGecko 列表，退出")
        return

    # 建立 symbol → list of coin_id 映射（一个 symbol 可能对应多个 coin）
    symbol_to_coins: dict[str, list[dict]] = {}
    for coin in cg_coins:
        sym = coin.get("symbol", "").upper()
        if sym in binance_symbols:
            symbol_to_coins.setdefault(sym, []).append(coin)

    print(f"  匹配到 {len(symbol_to_coins)} 个 Binance 期货代币")

    # Step 3: 逐个获取合约地址
    print(f"\n[3/3] 获取合约地址（共 {len(symbol_to_coins)} 个，每个需 ~1s）...")
    result = {}
    platform_map = {
        "binance-smart-chain": "bsc",
        "ethereum": "eth",
        "solana": "sol",
    }

    total = len(symbol_to_coins)
    for i, (symbol, coins) in enumerate(symbol_to_coins.items(), 1):
        print(f"  [{i}/{total}] {symbol}...", end=" ", flush=True)

        # 尝试每个匹配的 coin_id（有些 symbol 有多个 coin）
        found = False
        for coin in coins:
            coin_id = coin["id"]
            detail = get_coingecko_coin_detail(coin_id)
            if not detail:
                continue

            platforms = detail.get("platforms", {})
            addresses = {}
            for cg_platform, ftm_chain in platform_map.items():
                addr = platforms.get(cg_platform, "")
                if addr:
                    addresses[ftm_chain] = addr

            if addresses:
                result[symbol] = addresses
                chains = ", ".join(addresses.keys())
                print(f"OK ({chains})")
                found = True
                break

            # 限速
            if i % 10 == 0:
                time.sleep(2)

        if not found:
            print("SKIP (无地址)")

        # 限速：CoinGecko 免费 API 每分钟约 10-30 次
        time.sleep(1.5)

    # 保存结果
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"完成! 共 {len(result)} 个代币有地址")
    print(f"保存到: {OUTPUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
