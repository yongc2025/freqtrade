import pandas as pd
import glob
import os
import json
from datetime import datetime

# 配置
DATA_PATH = "d:/workspace/freqtrade-reference/user_data/data/binance/futures/*.feather"
TIMERANGE_START = "2025-01-01"
TIMERANGE_END = "2026-04-19"
EXCLUDE_COINS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "BNB/USDT:USDT"]
TOP_N = 40

def get_momentum_coins():
    files = glob.glob(DATA_PATH)
    # 只处理 -futures.feather 文件
    files = [f for f in files if "-futures.feather" in f]
    
    momentum_data = []
    
    for file in files:
        # 文件名格式: ZEC_USDT_USDT-1h-futures.feather
        base_name = os.path.basename(file)
        pair_part = base_name.split("-")[0] # ZEC_USDT_USDT
        parts = pair_part.split("_")
        if len(parts) >= 2:
            pair = f"{parts[0]}/{parts[1]}:{parts[2]}" if len(parts) == 3 else f"{parts[0]}/{parts[1]}"
        else:
            continue
            
        if pair in EXCLUDE_COINS:
            continue
            
        try:
            df = pd.read_feather(file)
            if df.empty:
                continue
            # 保证日期格式
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'], unit='ms')
            
            # 过滤时间段
            mask = (df['date'] >= TIMERANGE_START) & (df['date'] <= TIMERANGE_END)
            df_filtered = df.loc[mask].copy()
            
            if len(df_filtered) < 100:
                continue
            
            # 计算总交易额 (close * volume)
            df_filtered['quote_volume'] = df_filtered['close'] * df_filtered['volume']
            avg_quote_volume = df_filtered['quote_volume'].mean()
            
            # 计算波动率 (Std of returns)
            df_filtered['returns'] = df_filtered['close'].pct_change()
            volatility = df_filtered['returns'].std()
            
            momentum_data.append({
                "pair": pair,
                "avg_volume": avg_quote_volume,
                "volatility": volatility
            })
        except Exception as e:
            pass

    df_momentum = pd.DataFrame(momentum_data)
    if df_momentum.empty:
        return []
        
    # 按照平均交易额排序，选出流动性最好的前 100 个，再从中选波动率最高的前 40 个
    # 或者直接按交易额选前 40 (用户需求：每小时交易额排名前 40)
    top_volume_coins = df_momentum.sort_values(by="avg_volume", ascending=False).head(TOP_N)
    return top_volume_coins["pair"].tolist()

def create_config(coins, name):
    base_config_path = "d:/workspace/freqtrade-reference/user_data/config_mf_v2.json"
    with open(base_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 强制包含 BTC 用于策略逻辑参考
    if "BTC/USDT:USDT" not in coins:
        coins.insert(0, "BTC/USDT:USDT")
        
    config["exchange"]["pair_whitelist"] = coins
    
    output_path = f"d:/workspace/freqtrade-reference/user_data/config_phase_{name}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print(f"Created {output_path} with {len(coins)} coins")

if __name__ == "__main__":
    # 分解为 2025 和 2026 两个阶段，或者合在一起
    # 2025 全年
    TIMERANGE_START = "2025-01-01"
    TIMERANGE_END = "2025-12-31"
    coins_2025 = get_momentum_coins()
    if coins_2025:
        create_config(coins_2025, "v6_top40_2025")
        
    # 2026 至今
    TIMERANGE_START = "2026-01-01"
    TIMERANGE_END = "2026-04-19"
    coins_2026 = get_momentum_coins()
    if coins_2026:
        create_config(coins_2026, "v6_top40_2026")
