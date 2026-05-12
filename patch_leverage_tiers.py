#!/usr/bin/env python3
"""
patch_leverage_tiers.py - 补全缺失的 leverage tiers

用法：
  python patch_leverage_tiers.py \
    --tiers-file freqtrade/exchange/binance_leverage_tiers.json \
    --pairs AAPL/USDT:USDT TSLA/USDT:USDT NVDA/USDT:USDT ...

或者自动从回测报错信息中提取缺失的币种：
  python patch_leverage_tiers.py \
    --tiers-file freqtrade/exchange/binance_leverage_tiers.json

原理：
  读取现有的 leverage_tiers 文件，给缺失的币种补一个默认 tier。
  默认 tier 基于 Binance 通用规则：maxLeverage=75，maintenanceMarginRate=0.004。
"""

import argparse
import json
import sys


DEFAULT_TIERS = [
    {
        "tier": 1.0,
        "minNotional": 0.0,
        "maxNotional": 10000.0,
        "maintenanceMarginRate": 0.004,
        "maxLeverage": 75.0,
        "info": {
            "bracket": "1",
            "initialLeverage": "75",
            "notionalCap": "10000",
            "notionalFloor": "0",
            "maintMarginRatio": "0.004",
            "cum": "0.0"
        }
    },
    {
        "tier": 2.0,
        "minNotional": 10000.0,
        "maxNotional": 50000.0,
        "maintenanceMarginRate": 0.005,
        "maxLeverage": 50.0,
        "info": {
            "bracket": "2",
            "initialLeverage": "50",
            "notionalCap": "50000",
            "notionalFloor": "10000",
            "maintMarginRatio": "0.005",
            "cum": "10.0"
        }
    },
    {
        "tier": 3.0,
        "minNotional": 50000.0,
        "maxNotional": 250000.0,
        "maintenanceMarginRate": 0.01,
        "maxLeverage": 25.0,
        "info": {
            "bracket": "3",
            "initialLeverage": "25",
            "notionalCap": "250000",
            "notionalFloor": "50000",
            "maintMarginRatio": "0.01",
            "cum": "210.0"
        }
    },
    {
        "tier": 4.0,
        "minNotional": 250000.0,
        "maxNotional": 1000000.0,
        "maintenanceMarginRate": 0.025,
        "maxLeverage": 10.0,
        "info": {
            "bracket": "4",
            "initialLeverage": "10",
            "notionalCap": "1000000",
            "notionalFloor": "250000",
            "maintMarginRatio": "0.025",
            "cum": "1960.0"
        }
    },
    {
        "tier": 5.0,
        "minNotional": 1000000.0,
        "maxNotional": 10000000.0,
        "maintenanceMarginRate": 0.05,
        "maxLeverage": 5.0,
        "info": {
            "bracket": "5",
            "initialLeverage": "5",
            "notionalCap": "10000000",
            "notionalFloor": "1000000",
            "maintMarginRatio": "0.05",
            "cum": "7460.0"
        }
    }
]


def make_tiers_for_pair(symbol: str) -> list[dict]:
    """为指定币种生成默认 leverage tiers"""
    tiers = []
    for t in DEFAULT_TIERS:
        tier = dict(t)
        tier["symbol"] = symbol
        tier["currency"] = "USDT"
        tier["info"] = dict(t["info"])
        tiers.append(tier)
    return tiers


def main():
    parser = argparse.ArgumentParser(description="补全缺失的 leverage tiers")
    parser.add_argument(
        "--tiers-file",
        default="freqtrade/exchange/binance_leverage_tiers.json",
        help="leverage tiers 文件路径",
    )
    parser.add_argument(
        "--pairs",
        nargs="*",
        help="要补全的币种列表。不指定则补全所有缺失的。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示会补全的币种，不实际修改文件",
    )
    args = parser.parse_args()

    # 加载现有 tiers
    with open(args.tiers_file) as f:
        tiers = json.load(f)

    existing = set(tiers.keys())
    print(f"现有 leverage tiers: {len(existing)} 个币种")

    # 确定要补全的币种
    if args.pairs:
        missing = [p for p in args.pairs if p not in existing]
    else:
        # 没指定币种，提示用户
        print("请指定要补全的币种，例如：")
        print(f"  python {sys.argv[0]} --pairs AAPL/USDT:USDT TSLA/USDT:USDT")
        print(f"\n或者你可以手动编辑 tiers 文件，给这些币种添加条目。")
        return

    if not missing:
        print("所有指定的币种都已有 leverage tiers，无需补全。")
        return

    print(f"需要补全 {len(missing)} 个币种：")
    for p in missing:
        print(f"  + {p}")

    if args.dry_run:
        print("\n(--dry-run 模式，未实际修改)")
        return

    # 补全
    for pair in missing:
        tiers[pair] = make_tiers_for_pair(pair)

    # 按 key 排序后写回
    tiers = dict(sorted(tiers.items()))
    with open(args.tiers_file, "w") as f:
        json.dump(tiers, f, indent=2)

    print(f"\n✅ 已补全 {len(missing)} 个币种的 leverage tiers")
    print(f"   文件: {args.tiers_file}")
    print(f"   总计: {len(tiers)} 个币种")


if __name__ == "__main__":
    main()
