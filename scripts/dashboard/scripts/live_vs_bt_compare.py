import sqlite3
import pandas as pd
import json
import os
import glob
import zipfile
import io
from datetime import datetime

# 路径配置
live_db = r'd:/workspace/freqtrade-reference/user_data/tradesv3_momentum_live.sqlite'
bt_dir = r'd:/workspace/freqtrade-reference/user_data/backtest_results/'

def analyze():
    print("\n" + "="*80)
    print("      LIVE TRADES vs BACKTEST RESULTS (DAILY COMPARISON)")
    print("="*80)

    # 1. 寻找最新的回测结果
    bt_files = glob.glob(os.path.join(bt_dir, "**/*.zip"), recursive=True)
    if not bt_files:
        bt_files = glob.glob(os.path.join(bt_dir, "**/*.json"), recursive=True)
        bt_files = [f for f in bt_files if not f.endswith('.meta.json') and 'backtest-result' in os.path.basename(f)]

    if not bt_files:
        print(f"错误: 在 {bt_dir} 没找到任何回测结果。")
        return
        
    bt_res_path = max(bt_files, key=os.path.getctime)
    print(f"BT 数据源: {os.path.basename(bt_res_path)}")

    # 2. 加载实盘数据库
    try:
        conn = sqlite3.connect(live_db)
        query = "SELECT pair, close_profit as profit_ratio, open_date, close_date, (close_profit * 100) as profit_pct FROM trades WHERE is_open = 0"
        df_live = pd.read_sql_query(query, conn)
        conn.close()
        df_live['close_date'] = pd.to_datetime(df_live['close_date'])
        df_live = df_live[df_live['close_date'] >= '2026-04-01'].copy()
        df_live['date'] = df_live['close_date'].dt.date
    except Exception as e:
        print(f"读取实盘数据库失败: {e}")
        return

    # 3. 加载回测记录
    try:
        if bt_res_path.endswith('.zip'):
            with zipfile.ZipFile(bt_res_path, 'r') as z:
                json_files = [f for f in z.namelist() if f.endswith('.json') and not f.endswith('.meta.json')]
                with z.open(json_files[0]) as f:
                    data = json.load(f)
        else:
            with open(bt_res_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        strategy = list(data['strategy'].keys())[0]
        bt_trades = data['strategy'][strategy]['trades']
        df_bt = pd.DataFrame(bt_trades)
        df_bt['close_date'] = pd.to_datetime(df_bt['close_date'])
        df_bt = df_bt[df_bt['close_date'] >= '2026-04-01'].copy()
        df_bt['date'] = df_bt['close_date'].dt.date
        df_bt['profit_pct'] = df_bt['profit_ratio'] * 100
    except Exception as e:
        print(f"解析回测结果失败: {e}")
        return

    # 4. 每日对比计算
    daily_live = df_live.groupby('date').agg(
        trades=('pair', 'count'),
        profit=('profit_pct', 'sum')
    ).reset_index()

    daily_bt = df_bt.groupby('date').agg(
        trades=('pair', 'count'),
        profit=('profit_pct', 'sum')
    ).reset_index()

    # 合并每日数据
    comparison = pd.merge(daily_live, daily_bt, on='date', how='outer', suffixes=('_live', '_bt')).fillna(0)
    comparison = comparison.sort_values('date')

    print("\n[ 每日盈亏与交易单数对比 ]")
    print(f"{'日期':<12} | {'实盘单数':<8} | {'回测单数':<8} | {'实盘利润%':<10} | {'回测利润%':<10} | {'偏差%'}")
    print("-" * 80)
    for _, row in comparison.iterrows():
        diff = row['profit_live'] - row['profit_bt']
        print(f"{str(row['date']):<12} | {int(row['trades_live']):<8} | {int(row['trades_bt']):<8} | {row['profit_live']:<10.2f} | {row['profit_bt']:<10.2f} | {diff:+.2f}")

    print("\n" + "="*80)
    print(f"总计 (Live): 单数 {int(comparison['trades_live'].sum())}, 总利润 {comparison['profit_live'].sum():.2f}%")
    print(f"总计 (BT):   单数 {int(comparison['trades_bt'].sum())}, 总利润 {comparison['profit_bt'].sum():.2f}%")
    print("="*80)

if __name__ == "__main__":
    analyze()
