"""
Freqtrade 配置参数全解析 (Python格式)
参考自 config_full.example.json
"""

config = {
    # --- 基础架构 ---
    "$schema": "https:#schema.freqtrade.io/schema.json", # 验证配置格式的官方架构链接

    # --- 交易限制 (Trading Limits) ---
    "max_open_trades": 3,               # 机器人允许同时持有的最大仓位数量
    "stake_currency": "BTC",            # 结算货币（如 USDT, BTC），所有买入都用它支付
    "stake_amount": 0.05,               # 单笔订单投入数额。可填：固定数值、"unlimited" (全仓平分) 
    "available_capital": 1000,          # 明确限制机器人总共能动用的本金（防止动用钱包里不想交易的钱）
    "tradable_balance_ratio": 0.99,     # 账户可用资金的动用比例（留 1% 缓冲应对收手续费后的余额不足）
    "amend_last_stake_amount": false,   # 当余额不足以支付 stake_amount 时，是否允许自动减小最后一笔订单的仓位
    "last_stake_amount_min_ratio": 0.5, # 如果允许调小仓位，最小不能低于原数额的 50%
    "amount_reserve_percent": 0.05,     # 始终在账户里保留 5% 的结算货币作为备用资金

    # --- 运行环境 (Environment) ---
    "dry_run": true,                    # 是否开启模拟盘（true=虚拟交易，false=实盘对接API）
    "dry_run_wallet": 1000,             # 模拟盘开始时的虚拟初始资金（USDT/BTC等）
    "bot_name": "freqtrade",            # 给你的机器人起个名字（会在 Telegram 消息里显示）
    "initial_state": "running",         # 启动状态。默认 running，设为 stopped 则待命但不交易
    "force_entry_enable": false,        # 是否允许在 Telegram 中强制手动进场

    # --- 策略执行参数 (Strategy Execution) ---
    "timeframe": "5m",                  # 策略分析用的 K 线周期（如 1m, 5m, 1h, 1d）
    "trading_mode": "spot",             # 交易模式：spot (现货), futures (期货)
    "margin_mode": "isolated",          # 保证金模式（仅期货）：isolated (逐仓), cross (全仓)
    "leverage": 1,                      # 杠杆倍数（仅期货和部分现货杠杆支持）

    # --- 出场逻辑 (Exit Logic) ---
    "minimal_roi": {                    # 最小投资回报率表（静态止盈）
        "40": 0.0,                      # 持仓超过 40 分钟，利润 > 0% 就卖出
        "30": 0.01,                     # 持仓超过 30 分钟，利润 > 1% 就卖出
        "0": 0.04                       # 只要利润 > 4%，立刻卖出
    },
    "stoploss": -0.10,                  # 强制硬止盈/止损位（-0.10 表示亏损 10% 斩仓）
    "trailing_stop": false,             # 是否启用追踪止损
    "trailing_stop_positive": 0.005,    # 利润达到 0.5% 时转入动态追踪模式
    "trailing_stop_positive_offset": 0.0051, # 触发追踪后，价格回调多少（0.51%）时触发平仓
    "trailing_only_offset_is_reached": false, # 是否仅在利润达到 offset 比例后才激活追踪止损
    "use_exit_signal": true,            # 策略发出卖出信号时是否真的执行
    "exit_profit_only": false,          # 发出信号时，如果没赚钱（亏损中），是否拒绝执行该信号
    "exit_profit_offset": 0.0,          # 发出信号时，要求目标必须至少赚 0.x% 才允许卖出
    "ignore_roi_if_entry_signal": false,# 持仓中如果又出现了进场信号，是否停用 ROI 止盈（即继续加仓或持有）

    # --- 订单处理 (Order Handling) ---
    "unfilledtimeout": {                # 挂单超时处理
        "entry": 10,                    # 买单挂了 10 分钟没成交则撤单
        "exit": 10,                     # 卖单挂了 10 分钟没成交则撤单
        "unit": "minutes"               # 单位：minutes, seconds
    },
    "entry_pricing": {                  # 进场报价逻辑
        "price_side": "same",           # 定价时参考订单簿哪一侧 (ask/bid/same/other)
        "use_order_book": true,         # 是否参考实时订单簿
        "order_book_top": 1,            # 参考订单簿第 1 档（盘口价格）
        "check_depth_of_market": {
            "enabled": false,           # 是否检查深度，防止滑点过大
            "bids_to_ask_delta": 1      # 买卖价差阈值
        }
    },
    "order_types": {                    # 订单指令类型
        "entry": "limit",               # 进场用限价单 (limit) 或市价单 (market)
        "exit": "limit",                # 出场用限价单
        "emergency_exit": "market",     # 紧急退出（手动或异常）用市价单
        "stoploss": "market",           # 止损单设为市价
        "stoploss_on_exchange": false,  # 是否直接在交易所服务器挂止盈止损单
        "stoploss_price_type": "last"   # 止损参考价：last (最新价), mark (标记价), index (指数价)
    },

    # --- 选币系统 (Pairlists) ---
    "pairlists": [
        {"method": "StaticPairList"},    # 1. 使用固定的白名单
        {
            "method": "VolumePairList", # 2. 根据成交量动态选币
            "number_assets": 20,        # 挑选前 20 个币
            "sort_key": "quoteVolume",  # 按 24h 交易额排序
            "refresh_period": 1800      # 每半小时更换一次选币清单
        },
        {"method": "AgeFilter", "min_days_listed": 10},        # 过滤：必须上线超过 10 天
        {"method": "SpreadFilter", "max_spread_ratio": 0.005},# 过滤：买卖价差超过 0.5% 的不要
        {"method": "PriceFilter", "min_price": 0.00000010}    # 过滤：价格太低的垃圾币不要
    ],

    # --- 交易所设置 (Exchange) ---
    "exchange": {
        "name": "binance",              # 交易所名称（如 binance, gateio, okx, bybit）
        "key": "your_api_key",
        "secret": "your_api_secret",
        "pair_whitelist": ["ETH/USDT"], # 允许交易的币种清单（白名单）
        "pair_blacklist": ["BNB/USDT"], # 绝对禁止交易的币种（黑名单）
        "ccxt_config": {"timeout": 30000}, # 底层库选项（如超时时间 30s）
    },

    # --- 外部通知 (Telegram/API) ---
    "telegram": {
        "enabled": false,               # 是否开启电报通知
        "token": "bot_token",
        "chat_id": "your_id",
        "notification_settings": {
            "entry": "on",              # 开仓时发消息
            "exit": "on",               # 平仓时发消息
            "status": "on"              # 运行状态汇报
        }
    },
    "api_server": {
        "enabled": false,               # 是否开启 FreqUI 网页管理后台
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "username": "admin",
        "password": "password"
    },

    # --- 内部参数 (Internals) ---
    "db_url": "sqlite:#/tradesv3.sqlite", # 历史交易数据存储文件
    "internals": {
        "process_throttle_secs": 5      # 机器人循环逻辑间隔（建议 5-10 秒）
    },
    "dataformat_ohlcv": "json",         # 离线数据存储格式：json, hdf5, feather
    "strategy_path": "user_data/strategies/" # 寻找策略文件的默认文件夹
}