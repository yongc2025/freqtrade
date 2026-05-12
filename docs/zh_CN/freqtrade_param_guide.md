# Freqtrade 中文参数详解与新手配置建议

## 1. 交易所与API参数
- `exchange.name`：交易所名称，如 `bybit`、`binance`。
- `exchange.key` / `exchange.secret`：API密钥和私钥，实盘必填，回测/模拟可留空。
- `exchange.type`：现货用 `spot`，合约/期货用 `swap`。
- `exchange.ccxt_config` / `ccxt_async_config`：高级代理、超时等设置，一般默认。
- `exchange.enable_ws`：是否启用WebSocket，建议新手设为 `false`，只用REST。

## 2. 杠杆与交易模式
- `trading_mode`：
  - `spot`：现货模式
  - `futures`：期货/合约模式（如bybit、binance futures）
- `margin_mode`：
  - `isolated`：逐仓（推荐新手）
  - `cross`：全仓
- `leverage`：杠杆倍数，1为无杠杆，2及以上为杠杆交易。新手建议1倍，熟悉后可适当提高。
- `liquidation_buffer`：强平保护缓冲，建议0.05（5%），防止极端行情被强平。

## 3. 常用参数说明
- `max_open_trades`：最大同时持仓数，建议新手3-5。
- `stake_currency`：下单货币，期货一般为 `USDT`。
- `stake_amount`：每单投入金额，`unlimited`为全仓，或填写具体数值。
- `pair_whitelist`：允许交易的币对，建议新手只选主流币。
- `process_throttle_secs`：主循环间隔，建议10-30秒，防止API限流。
- `fee`：手续费率，bybit/币安期货一般0.0005。

## 4. 新手推荐配置片段
```json
"exchange": {
    "name": "bybit",
    "type": "swap",
    "enable_ws": false,
    ...
},
"trading_mode": "futures",
"margin_mode": "isolated",
"leverage": 1,
"liquidation_buffer": 0.05,
"max_open_trades": 3,
"stake_currency": "USDT",
"stake_amount": "unlimited",
"process_throttle_secs": 15,
"fee": 0.0005,
```

## 5. 注意事项
- 实盘前务必用 dry_run/回测充分验证策略。
- 杠杆越高风险越大，新手建议1倍。
- API密钥要妥善保管，切勿泄露。
- 期货模式下，务必理解强平、爆仓等风险。

---
如需更详细参数说明，可查阅官方文档或继续提问。