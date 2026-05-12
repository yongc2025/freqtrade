import json
import os
import pandas as pd
from datetime import datetime, timedelta

# 定义黑名单：排除回测时不想碰的主流币和稳定币
EXCLUDED_PAIRS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", 
    "ADA/USDT:USDT", "DOGE/USDT:USDT", "TRX/USDT:USDT", "LTC/USDT:USDT", 
    "LINK/USDT:USDT", "AVAX/USDT:USDT", "BNB/USDT:USDT"
]

def get_top_volume_pairs(data_dir, reference_date, limit=40):
    """
    模拟在 reference_date 这一天看到的过去 30 天成交额排行榜
    """
    pairs_volume = []
    end_dt = pd.to_datetime(reference_date).tz_localize('UTC')
    start_dt = end_dt - timedelta(days=30)
    
    if not os.path.exists(data_dir):
        print(f"Data directory not found: {data_dir}")
        return []

    files = [f for f in os.listdir(data_dir) if "-1h-futures.feather" in f]
    print(f"Found {len(files)} feather files items. Analyzing...")

    for file in files:
        pair = file.replace("-1h-futures.feather", "").replace("_", "/") + ":USDT"
        if pair in EXCLUDED_PAIRS:
            continue
            
        try:
            df = pd.read_feather(os.path.join(data_dir, file))
            # 确保日期是 UTC
            if df['date'].dt.tz is None:
                df['date'] = df['date'].dt.tz_localize('UTC')
            else:
                df['date'] = df['date'].dt.tz_convert('UTC')
                
            # 过滤出 reference_date 之前 30 天的数据
            mask = (df['date'] >= start_dt) & (df['date'] < end_dt)
            recent_df = df.loc[mask]
            
            if not recent_df.empty:
                # 计算平均每周期成交额 = Close * Volume
                avg_volume = (recent_df['close'] * recent_df['volume']).mean()
                pairs_volume.append((pair, avg_volume))
        except Exception as e:
            continue

    print(f"Computed volumes for {len(pairs_volume)} pairs.")
    # 按成交额排序
    pairs_volume.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in pairs_volume[:limit]]


def generate_monthly_configs():
    data_dir = "user_data/data/binance/futures"
    # 我们只需要一个大池子配置文件
    check_points = {
        "SuperPool_Top100": "2025-01-01"
    }
    
    base_config = {
        "max_open_trades": 10,
        "stake_currency": "USDT",
        "stake_amount": "unlimited",
        "tradable_balance_ratio": 0.95,
        "timeframe": "1h",
        "exchange": {
            "name": "binance",
            "type": "futures",
            "pair_whitelist": [],
            "pair_blacklist": [
                "(BSC)/.*", ".*REWARD/.*", ".*BEAR/.*", ".*BULL/.*", ".*UP/.*", ".*DOWN/.*", ".*BNB/.*"
            ]
        },
        "pairlists": [
            {
                "method": "StaticPairList"
            },
            {
                "method": "ShuffleFilter",
                "seed": 42
            }
        ]
    }

    for label, date in check_points.items():
        print(f"Selecting best 100 historical pairs for {label}...")
        # 我们选 100 个活跃币，由策略逻辑在其中实时挑选买点
        top_pairs = get_top_volume_pairs(data_dir, date, limit=100)
        
        if top_pairs:
            config = base_config.copy()
            config["exchange"]["pair_whitelist"] = top_pairs
            file_path = f"user_data/config_v6_rolling_{label}.json"
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Successfully generated: {file_path} with {len(top_pairs)} pairs.")
        else:
            print(f"No data found for {label}, skipping.")

if __name__ == "__main__":
    generate_monthly_configs()

