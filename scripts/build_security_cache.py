"""
批量生成 gmgn_security_cache.json

从 token_addresses.json 读取代币地址，
调用 gmgn-cli 获取 security + holders 数据，
写入 user_data/gmgn_security_cache.json 供策略使用。

依赖: gmgn-cli (npm install -g gmgn-cli 或本地 gmgn-skills)
用法: python scripts/build_security_cache.py [--limit N] [--chain sol|bsc|eth|base]

环境变量: GMGN_API_KEY (必须)
"""

import json
import os
import subprocess
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta


BASE_DIR = Path(__file__).parent.parent
TOKEN_DB_PATH = BASE_DIR / "user_data" / "token_addresses.json"
OUTPUT_PATH = BASE_DIR / "user_data" / "gmgn_security_cache.json"

# 策略关注的链（按优先级）
PRIORITY_CHAINS = ["eth", "bsc", "sol", "base", "arb", "avax", "polygon", "op", "sui", "ton", "tron"]

# gmgn-cli 路径（优先本地，其次全局）
GMGN_CLI_CANDIDATES = [
    str(BASE_DIR.parent / "gmgn-skills" / "dist" / "index.js"),
    "gmgn-cli",
]

# 每次 API 调用间隔（秒），防止限流
API_DELAY = 1.5


def find_gmgn_cli() -> str:
    """查找可用的 gmgn-cli"""
    for candidate in GMGN_CLI_CANDIDATES:
        if candidate.startswith("/"):
            if Path(candidate).exists():
                return candidate
        else:
            # 检查全局命令
            try:
                result = subprocess.run(
                    ["which", candidate],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return candidate
            except Exception:
                continue

    print("❌ 找不到 gmgn-cli")
    print("   请确保以下之一可用:")
    print("   1. cd gmgn-skills && npm install && npx tsc")
    print("   2. npm install -g gmgn-cli")
    sys.exit(1)


def call_gmgn(cli: str, *args) -> dict | None:
    """调用 gmgn-cli 并返回 JSON"""
    # 如果是 node 脚本，用 node 运行
    if cli.endswith(".js"):
        cmd = ["node", cli] + list(args)
    else:
        cmd = [cli] + list(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None
    except Exception as e:
        return None


def fetch_security(cli: str, chain: str, address: str) -> dict:
    """获取代币安全数据"""
    raw = call_gmgn(cli, "token", "security", "--chain", chain, "--address", address, "--raw")
    if not raw:
        return {}

    data = raw.get("data", raw)

    return {
        "rug_ratio": safe_float(data.get("rug_ratio", 0)),
        "is_honeypot": 1 if data.get("is_honeypot") in (True, "true", "yes", 1) else 0,
        "bundler_rate": safe_float(
            data.get("bundler_trader_amount_rate", data.get("bundler_rate", 0))
        ),
        "rat_trader_rate": safe_float(
            data.get("rat_trader_amount_rate", data.get("rat_trader_rate", 0))
        ),
        "liquidity": safe_float(data.get("liquidity", 0)),
    }


def fetch_holders(cli: str, chain: str, address: str) -> dict:
    """获取代币持有人数据（聪明钱 + 狙击手）"""
    raw = call_gmgn(cli, "token", "holders", "--chain", chain, "--address", address, "--limit", "50", "--raw")
    if not raw:
        return {}

    data = raw.get("data", raw)

    return {
        "smart_money_count": int(data.get("smart_degen_count", data.get("smart_money_count", 0)) or 0),
        "kol_count": int(data.get("renowned_wallets", data.get("renowned_count", 0)) or 0),
        "sniper_count": int(data.get("sniper_count", 0) or 0),
        "fresh_wallet_rate": safe_float(data.get("fresh_wallet_rate", 0)),
    }


def safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def load_token_db() -> dict:
    """加载 token_addresses.json"""
    if not TOKEN_DB_PATH.exists():
        print(f"❌ {TOKEN_DB_PATH} 不存在")
        print("   请先运行: python scripts/fetch_token_addresses.py")
        sys.exit(1)

    with open(TOKEN_DB_PATH, "r") as f:
        data = json.load(f)

    # 去掉 _meta
    data.pop("_meta", None)
    return data


def load_existing_cache() -> dict:
    """加载已有的缓存（增量更新）"""
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    """保存缓存"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="批量生成 gmgn_security_cache.json")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个代币（0=全部）")
    parser.add_argument("--chain", type=str, default="", help="只处理指定链（默认: 全部）")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已有缓存的代币")
    parser.add_argument("--delay", type=float, default=API_DELAY, help="API 调用间隔（秒）")
    args = parser.parse_args()

    print("=" * 60)
    print("GMGN 安全缓存生成工具")
    print("=" * 60)

    # 检查 API Key
    if not os.environ.get("GMGN_API_KEY"):
        print("\n⚠️  未设置 GMGN_API_KEY 环境变量")
        print("   gmgn-cli 需要 API Key 才能调用")
        print("   设置方法: export GMGN_API_KEY=your_key_here")
        print("   或创建 ~/.config/gmgn/.env 文件")
        sys.exit(1)

    # 查找 gmgn-cli
    cli = find_gmgn_cli()
    print(f"\n📦 使用 gmgn-cli: {cli}")

    # 加载数据
    token_db = load_token_db()
    cache = load_existing_cache()
    print(f"📄 token_addresses.json: {len(token_db)} 个代币")
    print(f"📦 已有缓存: {len(cache)} 条")

    # 筛选有地址的代币
    tokens_with_addr = {}
    for symbol, chains in token_db.items():
        if symbol == "_meta":
            continue
        if not isinstance(chains, dict) or not chains:
            continue
        # 按优先级选一条链
        selected_chain = None
        selected_addr = None
        for chain in PRIORITY_CHAINS:
            if chain in chains and chains[chain]:
                selected_chain = chain
                selected_addr = chains[chain]
                break
        if selected_chain and selected_addr:
            tokens_with_addr[symbol] = (selected_chain, selected_addr)

    print(f"🔗 有链上地址的代币: {len(tokens_with_addr)} 个")

    # 过滤链
    if args.chain:
        tokens_with_addr = {
            sym: (chain, addr)
            for sym, (chain, addr) in tokens_with_addr.items()
            if chain == args.chain
        }
        print(f"🔍 过滤链 {args.chain}: {len(tokens_with_addr)} 个")

    # 限制数量
    items = list(tokens_with_addr.items())
    if args.limit > 0:
        items = items[:args.limit]
        print(f"🔢 限制处理: {len(items)} 个")

    # 开始处理
    print(f"\n{'=' * 60}")
    print(f"开始获取数据 (间隔 {args.delay}s)")
    print(f"{'=' * 60}\n")

    success = 0
    skipped = 0
    failed = 0

    for i, (symbol, (chain, address)) in enumerate(items, 1):
        cache_key = f"{chain}:{address}"

        # 跳过已有缓存
        if args.skip_existing and (cache_key in cache or address in cache):
            print(f"  [{i}/{len(items)}] {symbol} ⏭️ 已有缓存")
            skipped += 1
            continue

        print(f"  [{i}/{len(items)}] {symbol} ({chain})...", end=" ", flush=True)

        # 获取 security
        sec = fetch_security(cli, chain, address)
        time.sleep(args.delay)

        # 获取 holders
        holders = fetch_holders(cli, chain, address)
        time.sleep(args.delay)

        if not sec and not holders:
            print("❌ 无数据")
            failed += 1
            continue

        # 合并数据
        combined = {**sec, **holders}

        # 同时写入 chain:address 和 address 两种 key（策略两种都查）
        cache[cache_key] = combined
        cache[address] = combined

        print(
            f"✅ rug={combined.get('rug_ratio', 0):.2f} "
            f"sm={combined.get('smart_money_count', 0)} "
            f"sniper={combined.get('sniper_count', 0)}"
        )
        success += 1

        # 每 10 个保存一次
        if i % 10 == 0:
            save_cache(cache)

    # 最终保存
    save_cache(cache)

    print(f"\n{'=' * 60}")
    print(f"✅ 完成!")
    print(f"   成功: {success}")
    print(f"   跳过: {skipped}")
    print(f"   失败: {failed}")
    print(f"   缓存总条目: {len(cache)}")
    print(f"   输出: {OUTPUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
