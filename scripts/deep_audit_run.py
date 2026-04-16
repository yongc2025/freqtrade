import zipfile
import json
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

"""
    深度审计脚本：最近一次回测结果全方位分析
"""
def get_latest_backtest_file():
    """自动获取 Freqtrade 最近一次的回测结果文件路径"""
    last_result_path = 'user_data/backtest_results/.last_result.json'
    if os.path.exists(last_result_path):
        with open(last_result_path, 'r') as f:
            last_data = json.load(f)
            return os.path.join('user_data/backtest_results', last_data['latest_backtest'])
    return None

def analyze_backtest():
    zip_path = get_latest_backtest_file()
    if not zip_path or not os.path.exists(zip_path):
        print("❌ 未找到有效回测结果")
        return

    print(f"📂 正在深度审计最新结果：{zip_path}")
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        json_file = z.namelist()[0]
        with z.open(json_file) as f:
            data = json.load(f)
            
    strategy_name = list(data['strategy'].keys())[0]
    results = data['strategy'][strategy_name]
    trades_data = results.get('trades', [])
    
    if not trades_data:
        print("❌ 结果中没有交易数据，无法进行深度审计")
        return

    # 1. 创建输出目录
    output_base_dir = os.path.join('user_data', 'backtest_analyzes')
    strategy_dir = os.path.join(output_base_dir, strategy_name)
    os.makedirs(strategy_dir, exist_ok=True)
    
    # 2. 准备数据
    df = pd.DataFrame(trades_data)
    df['open_date'] = pd.to_datetime(df['open_date'])
    df['close_date'] = pd.to_datetime(df['close_date'])
    df = df.sort_values('close_date').reset_index(drop=True)
    
    # 获取初始本金 (对数轴必须从正数开始)
    stake_raw = results.get('stake_amount', 1000)
    try:
        initial_capital = float(stake_raw)
    except (ValueError, TypeError):
        # 如果是字符串 (如 '1000 USDT')，提取数字
        import re
        match = re.search(r"(\d+\.?\d*)", str(stake_raw))
        initial_capital = float(match.group(1)) if match else 1000.0

    # 计算 净值 (Equity) = 初始本金 + 累计盈亏
    df['equity'] = initial_capital + df['profit_abs'].cumsum()
    
    # 提前计算回撤数据 (基于净值)
    df['max_equity'] = df['equity'].cummax()
    df['drawdown'] = df['equity'] - df['max_equity']
    df['drawdown_pct'] = (df['equity'] / df['max_equity']) - 1
    
    # 3. 计算对齐文档要求的五大类指标
    total_trades = len(df)
    win_trades = len(df[df['profit_abs'] > 0])
    loss_trades = len(df[df['profit_abs'] < 0])
    
    profit_total_abs = results.get('profit_total_abs', 0)
    profit_total_pct = results.get('profit_total_pct', 0) if isinstance(results.get('profit_total_pct'), float) else results.get('profit_total', 0)*100
    max_drawdown_per = results.get('max_drawdown_account', 0)
    cagr = results.get('cagr', 0)
    
    # --- 新增：从 Freqtrade 提取原生关键指标 ---
    sqn = results.get('sqn', 0)
    profit_factor = results.get('profit_factor', 0)
    expectancy = results.get('expectancy', 0)
    market_change = results.get('market_change', 0) * 100
    alpha = profit_total_pct - market_change
    
    # 计算平均持仓时间 (从 df 计算以防止 results 中字段缺失)
    df['trade_duration_s'] = (df['close_date'] - df['open_date']).dt.total_seconds()
    
    def format_duration(seconds):
        if pd.isna(seconds) or seconds <= 0: return "00:00"
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        m = int((seconds % 3600) // 60)
        if d > 0: return f"{d}d {h:02}:{m:02}"
        return f"{h:02}:{m:02}"

    win_duration_avg = format_duration(df[df['profit_abs'] > 0]['trade_duration_s'].mean())
    loss_duration_avg = format_duration(df[df['profit_abs'] < 0]['trade_duration_s'].mean())
    
    # 获取最大回撤持续天数 (手动计算: Longest Underwater Period)
    # 策略: 记录上一个最高峰的时间点，计算当前时间与高峰时间的差值
    df['is_new_high'] = df['equity'] >= df['equity'].cummax()
    df['last_high_date'] = df.loc[df['is_new_high'], 'close_date']
    df['last_high_date'] = df['last_high_date'].ffill()
    # 对于回测开始时如果第一笔就是回撤的情况，填充第一笔的 open_date
    if df['last_high_date'].iloc[0] is pd.NaT:
        df['last_high_date'].fillna(df['open_date'].iloc[0], inplace=True)
    
    df['underwater_duration'] = df['close_date'] - df['last_high_date']
    computed_mdd_days = df['underwater_duration'].max().days
    
    # 优先尝试从官方汇总字段获取，若没有则使用计算出的结果
    mdd_duration_raw = results.get('max_drawdown_duration', results.get('max_drawdown_duration_days', None))
    if isinstance(mdd_duration_raw, str) and 'days' in mdd_duration_raw:
        mdd_days = mdd_duration_raw.split(' ')[0]
    elif mdd_duration_raw and mdd_duration_raw != 'N/A':
        mdd_days = str(int(float(mdd_duration_raw)))
    else:
        mdd_days = str(computed_mdd_days)

    # 辅助：月度重采样
    df_m = df.resample('M', on='close_date')['profit_abs'].sum()
    
    # 计算连续盈亏
    df['win'] = df['profit_abs'] > 0
    df['consecutive_win'] = df['win'].groupby((df['win'] != df['win'].shift()).cumsum()).cumcount() + 1
    max_consecutive_win = df[df['win']]['consecutive_win'].max() if win_trades > 0 else 0
    df['loss'] = df['profit_abs'] < 0
    df['consecutive_loss'] = df['loss'].groupby((df['loss'] != df['loss'].shift()).cumsum()).cumcount() + 1
    max_consecutive_loss = df[df['loss']]['consecutive_loss'].max() if loss_trades > 0 else 0

    # 计算回撤阈值次数 (对齐邢不行标准: 盈亏比、回撤次数)
    dd_abs_limit = profit_total_abs if profit_total_abs > 0 else 1000
    count_dd_5 = len(df[df['drawdown'] < -dd_abs_limit * 0.05])
    count_dd_10 = len(df[df['drawdown'] < -dd_abs_limit * 0.10])
    count_dd_15 = len(df[df['drawdown'] < -dd_abs_limit * 0.15])

    # --- 模块化统计指标 (5大类) ---
    metrics_categorized = {
        "收益指标 (8个)": {
            "累计收益率": f"{profit_total_pct:.2f}%",
            "年化收益率": f"{cagr*100:.2f}%",
            "超额收益(Alpha)": f"{alpha:.2f}%",
            "市场涨跌幅": f"{market_change:.2f}%",
            "月度平均收益": f"{df_m.mean():.2f} USDT",
            "正收益月占比": f"{(len(df_m[df_m > 0]) / len(df_m) * 100):.2f}%" if len(df_m) > 0 else "0%",
            "最佳月度收益": f"{df_m.max():.2f} USDT",
            "最差月度收益": f"{df_m.min():.2f} USDT"
        },
        "风险指标 (8个)": {
            "最大回撤": f"-{(max_drawdown_per*100):.2f}%",
            "最大回撤天数": f"{mdd_days} 天",
            "获利因子": f"{profit_factor:.2f}",
            "月度收益标差": f"{df_m.std():.2f} USDT",
            "下行标准差": f"{df_m[df_m<0].std():.2f} USDT" if not df_m[df_m<0].empty else "0",
            "回撤>5%次数": count_dd_5,
            "回撤>10%次数": count_dd_10,
            "回撤>15%次数": count_dd_15
        },
        "风险调整收益 (5个)": {
            "夏普比率": f"{results.get('sharpe', 0):.2f}",
            "索提诺比率": f"{results.get('sortino', 0):.2f}",
            "卡玛比率": f"{results.get('calmar', 0):.2f}",
            "SQN (系统质量)": f"{sqn:.2f}",
            "收益回撤比": f"{abs(profit_total_pct / (max_drawdown_per*100) if max_drawdown_per != 0 else 0):.2f}"
        },
        "交易统计 (7个)": {
            "总交易笔数": f"{total_trades} 笔",
            "交易胜率": f"{(win_trades/total_trades*100):.2f}%" if total_trades > 0 else "0%",
            "盈亏比": f"{abs(df[df['profit_abs']>0]['profit_abs'].mean() / df[df['profit_abs']<0]['profit_abs'].mean()):.2f}" if loss_trades > 0 else "N/A",
            "交易期望值": f"{expectancy:.4f}",
            "最大连盈/连亏": f"{max_consecutive_win} / {max_consecutive_loss}",
            "盈利单均持仓": f"{win_duration_avg}",
            "亏损单均持仓": f"{loss_duration_avg}"
        },
        "仓位统计 (8个)": {
            "多空笔数比": f"{len(df[~df['is_short']])}L / {len(df[df['is_short']])}S",
            "被拒绝信号数": f"{results.get('rejected_signals', 0)}",
            "最佳交易品种": f"{results.get('best_pair', {}).get('key', 'N/A')}",
            "最差交易品种": f"{results.get('worst_pair', {}).get('key', 'N/A')}",
            "平均品种数": f"{len(results.get('results_per_pair', []))}",
            "日均交易笔数": f"{results.get('trades_per_day', 0):.2f}",
            "最大并发数": f"{results.get('max_open_trades', 0)}",
            "平均单笔头寸": f"{results.get('avg_stake_amount', 0):.2f} USDT"
        }
    }


    # 计算最大回测区间 (用于阴影标注)
    max_dd_idx = df['drawdown_pct'].idxmin()
    max_dd_end_time = df.loc[max_dd_idx, 'close_date']
    # 寻找回撤开始点：在最大回撤点之前，净值最后一次达到最高峰的时刻
    before_dd = df.loc[:max_dd_idx]
    peak_times = before_dd[before_dd['equity'] == before_dd['max_equity']]['close_date']
    max_dd_start_time = peak_times.iloc[-1] if not peak_times.empty else df['close_date'].iloc[0]

    # 计算月度/季度/年度数据
    df['year_str'] = df['close_date'].dt.year.astype(str)
    df['quarter'] = df['close_date'].dt.quarter
    df['month_str'] = df['close_date'].dt.strftime('%Y-%m')
    
    # --- 6.1 年度对比表格数据 ---
    annual_stats = []
    for year, group in df.groupby('year_str'):
        y_profit_pct = (group['profit_abs'].sum() / initial_capital * 100)
        y_max_dd = group['drawdown_pct'].min() * 100
        y_sharpe = (group['profit_abs'].mean() / group['profit_abs'].std() * (len(group)**0.5)) if len(group)>1 and group['profit_abs'].std() != 0 else 0
        y_win_months = group.resample('M', on='close_date')['profit_abs'].sum()
        y_win_ratio = f"{len(y_win_months[y_win_months > 0])}/{len(y_win_months)}"
        annual_stats.append({
            '年份': year,
            '收益率': f"{y_profit_pct:.2f}%",
            '最大回撤': f"{y_max_dd:.2f}%",
            '夏普比率': f"{y_sharpe:.2f}",
            '正收益月数': y_win_ratio,
            '月均收益率': f"{(y_profit_pct/len(y_win_months)):.2f}%" if len(y_win_months)>0 else "0%"
        })

    # --- 4.1 找出最大的5次回撤 ---
    df['is_dd'] = df['drawdown'] < 0
    df['dd_group'] = (df['is_dd'] != df['is_dd'].shift()).cumsum()
    dd_events = []
    for _, group in df[df['is_dd']].groupby('dd_group'):
        start_t = group['close_date'].min()
        end_t = group['close_date'].max()
        peak_t = group.loc[group['equity'].idxmin(), 'close_date']
        depth = group['drawdown_pct'].min() * 100
        # 恢复时间需在当前回撤结束后的第一个净值创新高点
        recovery_df = df[df['close_date'] > end_t]
        recovery_point = recovery_df[recovery_df['equity'] >= group['max_equity'].iloc[0]]
        recovery_t = recovery_point['close_date'].iloc[0] if not recovery_point.empty else "未恢复"
        
        dd_events.append({
            'rank': 0,
            'depth': depth,
            'start': start_t.strftime('%Y-%m-%d'),
            'valley': peak_t.strftime('%Y-%m-%d'),
            'recovery': recovery_t.strftime('%Y-%m-%d') if isinstance(recovery_t, datetime) else recovery_t,
            'duration': (end_t - start_t).days
        })
    top5_drawdowns = sorted(dd_events, key=lambda x: x['depth'])[:5]
    for i, dd in enumerate(top5_drawdowns): dd['rank'] = i + 1

    # --- 综合评分逻辑 (满分100) ---
    score_profit = min(30, (profit_total_pct / 50) * 30) if profit_total_pct > 0 else 0 # 50%收益拿满30分
    score_risk = max(0, 30 + (max_drawdown_per * 100 / 20) * -30) # 20%回撤扣完30分
    score_sharp = min(20, (results.get('sharpe', 0) / 2) * 20) # 夏普2.0拿满20分
    score_stability = min(20, (len(df_m[df_m>0])/len(df_m)*20)) if len(df_m)>0 else 0 # 胜率月20分
    avg_score = score_profit + score_risk + score_sharp + score_stability
    score_level = "优秀" if avg_score >= 85 else "良好" if avg_score >= 70 else "一般" if avg_score >= 60 else "风险极高"

    # --- 转换收益为百分比 (%) 对其邢不行标准 ---
    yearly_p = (df.groupby('year_str')['profit_abs'].sum() / initial_capital * 100)
    monthly_p = (df.groupby('month_str')['profit_abs'].sum() / initial_capital * 100)
    
    # 季度数据并补全 Q1-Q4
    q_data_raw = df.groupby(['year_str', 'quarter'])['profit_abs'].sum() / initial_capital * 100
    q_data = q_data_raw.unstack().fillna(0)
    for q in [1, 2, 3, 4]:
        if q not in q_data.columns:
            q_data[q] = 0.0
    q_data = q_data[[1, 2, 3, 4]] # 强制排序

    # --- 6. 统计利润构成 ---
    total_net_profit = df['profit_abs'].sum()
    # 模拟手续费和资金费 (使用 Series 处理以防列缺失)
    total_fees = abs(df.get('fee_open_cost', pd.Series([0], dtype=float)).sum() + 
                     df.get('fee_close_cost', pd.Series([0], dtype=float)).sum())
    total_funding = df.get('funding_fees', pd.Series([0], dtype=float)).sum()
    # 如果结果里没有手续费值，则根据 cost 推算 (估算)
    if total_fees == 0:
        cost_series = df.get('cost', df.get('stake_amount', pd.Series([initial_capital]*len(df), dtype=float)))
        total_fees = cost_series.sum() * 0.0012 # 这里的 0.0012 是典型费率
    
    gross_profit = total_net_profit + total_fees - total_funding

    fig = make_subplots(
        rows=3, cols=4,
        subplot_titles=(
            '1. 账户净值(Equity)对数轴 (红色阴影=MDD区间)', '2. 回撤比例及时序分析 (%)',
            '3. 年度收益率分布 (%)', '4. 季度收益热力图 (红亏绿盈 %)', '5. 利润构成汇总 (利润 vs 成本)', '6. 月度收益率时序 (%)',
            '7. 收益率分布直方图', '8. 杠杆比例', '9. 多空分布', '10. 持仓品种数堆叠'
        ),
        specs=[[{"colspan": 2}, None, {"colspan": 2}, None],
               [{}, {}, {"type": "domain"}, {}],
               [{}, {}, {}, {}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )

    # 1. 净值曲线 (Equity 对数坐标)
    fig.add_trace(go.Scatter(x=df['close_date'], y=df['equity'], name='净值', line=dict(color='#2c3e50', width=2)), row=1, col=1)
    fig.add_vrect(x0=max_dd_start_time, x1=max_dd_end_time, fillcolor="rgba(231, 76, 60, 0.3)", opacity=0.5, layer="below", line_width=0, row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)

    # 2. 回撤曲线
    fig.add_trace(go.Scatter(x=df['close_date'], y=df['drawdown_pct']*100, name='回撤%', fill='tozeroy', fillcolor='rgba(149, 165, 166, 0.4)', line=dict(color='#7f8c8d')), row=1, col=3)

    # 3. 年度收益
    fig.add_trace(go.Bar(x=yearly_p.index, y=yearly_p.values, text=yearly_p.values.round(2).astype(str)+'%', textposition='auto', marker_color='#3498db'), row=2, col=1)

    # 4. 季度热力图
    fig.add_trace(go.Heatmap(z=q_data.values, x=[f'Q{i}' for i in q_data.columns], y=q_data.index, colorscale='RdYlGn', showscale=True, colorbar=dict(thickness=10, len=0.3, y=0.5, x=0.35, title='%')), row=2, col=2)

    # 5. 利润构成 (Pie Chart 替代，展示在 2,3)
    comp_labels = ['纯利润 (Net)', '手续费 (Fees)', '资金费 (Funding)']
    comp_values = [max(0, total_net_profit), total_fees, abs(total_funding)]
    fig.add_trace(go.Pie(labels=comp_labels, values=comp_values, hole=.4, marker=dict(colors=['#2ecc71', '#e74c3c', '#f1c40f']), textinfo='percent+label'), row=2, col=3)

    # 6. 月度收益
    colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in monthly_p.values]
    fig.add_trace(go.Bar(x=monthly_p.index, y=monthly_p.values, marker_color=colors), row=2, col=4)

    # 下方 4 个图
    fig.add_trace(go.Histogram(x=df['profit_ratio'], nbinsx=50, marker_color='#9b59b6'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df['close_date'], y=[1.0]*len(df), name='杠杆', line=dict(color='#f1c40f')), row=3, col=2)
    fig.add_trace(go.Bar(x=['多头', '空头'], y=[len(df[~df['is_short']]), len(df[df['is_short']])], marker_color=['#3498db', '#e74c3c']), row=3, col=3)
    
    pair_counts = df.groupby('close_date')['pair'].nunique()
    fig.add_trace(go.Scatter(x=pair_counts.index, y=pair_counts.values, fill='tozeroy', line=dict(color='#1abc9c')), row=3, col=4)

    # 统一布局
    fig.update_layout(height=1300, width=1580, showlegend=False, template="plotly_white", title_text=f"深度审计仪表盘: {strategy_name}")
    fig.update_xaxes(tickformat="%Y-%m-%d")

    plots_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})

    # --- 滚动分析 (动态适应窗口) ---
    df_daily = df.set_index('close_date').resample('D')['profit_abs'].sum().fillna(0)
    df_daily_cum = (initial_capital + df_daily.cumsum())
    
    # 滚动收益率：如果有365天则用365天，否则用已有的最大天数，最小30天
    rolling_12m_ret = (df_daily_cum / df_daily_cum.shift(365).fillna(df_daily_cum.iloc[0]) - 1) * 100
    
    daily_ret = df_daily_cum.pct_change()
    # 夏普比率和回撤增加 min_periods=30，让短周期回测也能看到趋势
    rolling_sharpe = (daily_ret.rolling(window=365, min_periods=30).mean() / daily_ret.rolling(window=365, min_periods=30).std()) * (252**0.5)
    rolling_peak = df_daily_cum.rolling(window=365, min_periods=30).max()
    rolling_mdd = (df_daily_cum / rolling_peak - 1) * 100

    fig_rolling = make_subplots(rows=3, cols=1, subplot_titles=('12个月滚动收益率 (%)', '12个月滚动夏普比率', '12个月滚动最大回撤 (%)'), vertical_spacing=0.1)
    fig_rolling.add_trace(go.Scatter(x=rolling_12m_ret.index, y=rolling_12m_ret, name='12个月滚动收益率', line=dict(color='#3498db')), row=1, col=1)
    fig_rolling.add_hline(y=0.0, line_dash="dash", line_color="black", row=1, col=1)
    fig_rolling.add_trace(go.Scatter(x=rolling_sharpe.index, y=rolling_sharpe, name='12个月滚动夏普', line=dict(color='#2ecc71')), row=2, col=1)
    fig_rolling.add_hline(y=1.0, line_dash="dash", line_color="orange", row=2, col=1); fig_rolling.add_hline(y=2.0, line_dash="dash", line_color="red", row=2, col=1)
    fig_rolling.add_trace(go.Scatter(x=rolling_mdd.index, y=rolling_mdd, fill='tozeroy', fillcolor='rgba(231, 76, 60, 0.4)', name='12个月滚动回撤', line=dict(color='#e74c3c')), row=3, col=1)
    fig_rolling.update_layout(height=800, showlegend=False, template="plotly_white", margin=dict(t=50, b=50))
    rolling_plots_html = fig_rolling.to_html(full_html=False, include_plotlyjs='cdn')

    # --- 最终 HTML 报告生成 ---
    # 策略评价逻辑 (动态生成)
    fee_pct = (total_fees / total_net_profit * 100) if total_net_profit > 0 else 100
    
    # 1. 盈利评价逻辑
    if cagr > 0.5 and results.get('sharpe', 0) > 1.5:
        profit_eval_text = f"年化收益率达到 {cagr*100:.2f}%，且夏普比率稳健，展示了极强的 Alpha 提取能力，在扣除摩擦成本后仍具备商业实盘水准。"
    elif cagr > 0.3:
        profit_eval_text = f"年化收益率 {cagr*100:.2f}% 表现尚可，但收益分布不均，需警惕个别品种暴涨带来的虚假繁荣。"
    else:
        profit_eval_text = f"年化收益率为 {cagr*100:.2f}%，盈利能力偏弱。考虑到当前 {fee_pct:.1f}% 的手续费磨损，该策略很难在实盘中产生可观净资产增幅。"

    # 2. 风险评价逻辑
    if max_drawdown_per < 0.15:
        risk_eval_text = f"最大回撤仅为 {max_drawdown_per*100:.2f}%，风险管理机制非常出色。在过去的回撤事件中，大多能在较短时间内实现净值修复。"
    elif max_drawdown_per < 0.3:
        risk_eval_text = f"最大回撤 {max_drawdown_per*100:.2f}% 属于中等风险等级。需重点复核 Top 5 回撤穿透表中的持续时间，防止由于长时间横盘导致的信心丧失。"
    else:
        risk_eval_text = f"警告：最大回撤高达 {max_drawdown_per*100:.2f}%，已经触及风控红线。该策略在遭遇极端行情时可能面临腰斩风险，严禁在不加外部风控的情况下实盘。"

    # 3. 成本/综合建议
    if fee_pct > 25:
        conclusion_text = f"注意：该策略的手续费占比高达 {fee_pct:.1f}%，属于典型的'给交易所打工'策略。建议大幅降低交易频率或筛选涨幅更大的信号。"
    elif avg_score >= 80:
        conclusion_text = "策略综合表现优秀。建议进行为期 4-8 周的小资金实盘前瞻测试，以确认回测与实盘的撮合一致性。"
    else:
        conclusion_text = "策略目前仍处于 Draft 阶段。建议针对滚动夏普较低的年份进行参数敏感性分析，寻找 Alpha 衰减的根源。"

    # 准备表格 HTML
    annual_tbody = "".join([f"<tr><td>{s['年份']}</td><td>{s['收益率']}</td><td>{s['最大回撤']}</td><td>{s['夏普比率']}</td><td>{s['正收益月数']}</td><td>{s['月均收益率']}</td></tr>" for s in annual_stats])
    dd_tbody = "".join([f"<tr><td>{d['rank']}</td><td>{d['depth']:.2f}%</td><td>{d['start']}</td><td>{d['valley']}</td><td>{d['recovery']}</td><td>{d['duration']} 天</td></tr>" for d in top5_drawdowns])

    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>{strategy_name} 深度审计报告</title>
        <style>
            body {{ font-family: 'Segoe UI', Microsoft YaHei, sans-serif; background-color: #f7f9fc; margin: 0; padding: 20px; }}
            .container {{ max-width: 1600px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 15px 40px rgba(0,0,0,0.1); padding: 40px; }}
            .header-info {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }}
            .persona-box {{ background: {"#2ecc71" if avg_score >= 80 else "#e74c3c"}; color: white; padding: 18px 30px; border-radius: 10px; font-weight: 800; font-size: 16px; flex-grow: 1; margin-left: 50px; border-left: 10px solid {"#27ae60" if avg_score >= 80 else "#c0392b"}; }}
            .section-title {{ font-size: 20px; color: #2c3e50; border-left: 6px solid #3498db; padding-left: 15px; margin: 40px 0 20px 0; font-weight: bold; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 30px; }}
            .metric-card {{ background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 0; }}
            .metric-header {{ background: #2c3e50; color: white !important; font-weight: 800; padding: 10px; text-align: center; border-radius: 8px 8px 0 0; font-size: 14px; font-family: "Microsoft YaHei"; }}
            .metric-body {{ padding: 12px; }}
            .metric-row {{ display: flex; justify-content: space-between; font-size: 13px; margin: 6px 0; }}
            .metric-label {{ font-weight: 800; color: #333; }}
            .metric-value {{ font-weight: bold; color: #1a73e8; }}
            .data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
            .data-table th {{ background: #2c3e50; color: white; padding: 12px; text-align: center; font-size: 14px; }}
            .data-table td {{ padding: 12px; border: 1px solid #eee; text-align: center; font-size: 13px; color: #333; }}
            .eval-report {{ background: #f8f9fa; border: 1px solid #ddd; border-radius: 10px; padding: 25px; margin-top: 50px; }}
            .score-badge {{ display: inline-block; background: #3498db; color: white; padding: 5px 15px; border-radius: 20px; font-size: 24px; font-weight: 900; margin-top: 10px; }}
            .footer {{ text-align: center; color: #9aa0a6; font-size: 12px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-info">
                <div>
                    <h1 style="margin:0; color:#2c3e50;">{strategy_name} 深度审计报告</h1>
                    <p style="color:#666; font-size:14px; margin-top:10px;">回测区间: {df['close_date'].min().strftime('%Y-%m-%d')} 至 {df['close_date'].max().strftime('%Y-%m-%d')} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                </div>
            </div>

            <div class="section-title">一、 策略统计指标全集</div>
            <div class="metrics-grid">
    """

    for category, items in metrics_categorized.items():
        html_template += f"""
                <div class="metric-card">
                    <div class="metric-header">{category}</div>
                    <div class="metric-body">
        """
        for label, val in items.items():
            html_template += f'<div class="metric-row"><span class="metric-label">{label}</span><span class="metric-value">{val}</span></div>'
        html_template += "</div></div>"

    html_template += f"""
            </div>
            <div class="section-title">二、 核心审计仪表盘</div>
            <div class="chart-area">{plots_html}</div>
            <div class="section-title">三、 年度业绩对比分析</div>
            <table class="data-table">
                <thead><tr><th>年份</th><th>期间收益率</th><th>最大回撤</th><th>夏普比率</th><th>正收益月数</th><th>月均收益率</th></tr></thead>
                <tbody>{annual_tbody}</tbody>
            </table>
            <div class="section-title">四、 回撤详细穿透 (Top 5 事件)</div>
            <table class="data-table">
                <thead><tr><th>排名</th><th>回撤幅度</th><th>开始时间</th><th>谷底时间</th><th>恢复时间</th><th>持续天数</th></tr></thead>
                <tbody>{dd_tbody}</tbody>
            </table>
            <div class="section-title">五、 12个月滚动风险分析</div>
            <div class="chart-area">{rolling_plots_html}</div>
            <div class="eval-report">
                <h1 style="text-align:center; color:#2c3e50;">策略综合评估报告 (Final Audit)</h1>
                <div style="display: flex; gap: 40px; margin-top: 20px;">
                    <div class="eval-item" style="flex:1;">
                        <div class="eval-label" style="font-weight:bold; font-size:18px; color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:5px;">1. 盈利能力评价</div>
                        <div class="eval-text" style="margin-top:10px; color:#555; line-height:1.6; font-size:14px;">
                            {profit_eval_text}
                        </div>
                    </div>
                    <div class="eval-item" style="flex:1;">
                        <div class="eval-label" style="font-weight:bold; font-size:18px; color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:5px;">2. 风险控制评价</div>
                        <div class="eval-text" style="margin-top:10px; color:#555; line-height:1.6; font-size:14px;">
                            {risk_eval_text}
                        </div>
                    </div>
                    <div class="eval-item" style="flex:1;">
                        <div class="eval-label" style="font-weight:bold; font-size:18px; color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:5px;">3. 审计建议</div>
                        <div class="eval-text" style="margin-top:10px; color:#555; line-height:1.6; font-size:14px;">
                            {conclusion_text}
                        </div>
                    </div>
                </div>
                <div style="text-align: center; border-top: 2px solid #ddd; padding-top: 20px;">
                    <span style="font-size:18px; color:#666;">量化核心审计总分</span><br/>
                    <div class="score-badge">{avg_score:.1f} / 100</div>
                </div>
            </div>
            <div class="footer">Freqtrade Quant Audit System Powered by Gemini 3 Flash (Preview)</div>
        </div>
    </body>
    </html>
    """
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(strategy_dir, f"{strategy_name}_report_{timestamp}.html")
    with open(report_file, 'w', encoding='utf-8') as f: f.write(html_template)
    latest_link = os.path.join(strategy_dir, f"{strategy_name}_latest_report.html")
    with open(latest_link, 'w', encoding='utf-8') as f: f.write(html_template)

    print(f"✅ 审计报告已成功生成：{report_file}")
    print(f"🔗 最新报告快捷访问：{latest_link}")

if __name__ == "__main__":
    analyze_backtest()

