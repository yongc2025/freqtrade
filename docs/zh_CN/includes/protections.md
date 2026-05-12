## 保护机制 (Protections)

保护机制通过在特定时间段内临时停止单个交易对或所有交易对的交易，来保护您的策略免受意外事件和市场状况的影响。
所有保护的结束时间都会向上舍入到下一个 K 线收盘，以避免在 K 线内部发生突然且意料之外的买入。

!!! Tip "使用技巧"
    并非所有保护机制都适用于所有策略，参数需要针对您的策略进行调整以提高性能。

    每个保护机制都可以使用不同的参数配置多次，以实现不同层级的保护（短期/长期）。

!!! Note "回测"
    回测和超参数优化 (hyperopt) 支持保护机制，但必须通过使用 `--enable-protections` 标志显式启用。

### 可用保护机制

* [`StoplossGuard`](#stoploss-guard) 如果在一定时间窗口内发生了特定数量的止损，则停止交易。
* [`MaxDrawdown`](#maxdrawdown) 如果达到最大回撤，则停止交易。
* [`LowProfitPairs`](#low-profit-pairs) 锁定利润较低的交易对。
* [`CooldownPeriod`](#cooldown-period) 在交易卖出后，不要立即开仓新的交易。

### 所有保护机制的通用设置

| 参数 | 描述 |
|------------|-------------|
| `method` | 要使用的保护机制名称。<br> **数据类型:** 字符串，选自 [可用保护机制](#available-protections) |
| `stop_duration_candles` | 应该设置多少根 K 线的锁定时长？ <br> **数据类型:** 正整数（单位：K 线） |
| `stop_duration` | 应该设置多少分钟的锁定时长？ <br>不能与 `stop_duration_candles` 同时使用。<br> **数据类型:** 浮点数（单位：分钟） |
| `lookback_period_candles` | 仅考虑在过去 `lookback_period_candles` 根 K 线内完成的交易。此设置可能会被某些保护机制忽略。<br> **数据类型:** 正整数（单位：K 线） |
| `lookback_period` | 仅考虑在 `current_time - lookback_period` 之后完成的交易。<br>不能与 `lookback_period_candles` 同时使用。<br>此设置可能会被某些保护机制忽略。<br> **数据类型:** 浮点数（单位：分钟） |
| `trade_limit` | 所需的最少交易数量（并非所有保护机制都使用）。<br> **数据类型:** 正整数 |
| `unlock_at` | 定期解锁交易的时间（并非所有保护机制都使用）。<br> **数据类型:** 字符串 <br>**输入格式:** "HH:MM" (24 小时制) |

!!! Note "持续时长"
    持续时长（`stop_duration*` 和 `lookback_period*` 可以用分钟或 K 线定义）。
    为了在测试不同时间框架时提供更多灵活性，以下所有示例都将使用 "K 线" 定义。

#### 止损保护 (Stoploss Guard)

`StoplossGuard` 选择在 `lookback_period` 分钟（或使用 `lookback_period_candles` 时对应的 K 线数）内完成的所有交易。
如果达到 `trade_limit` 数量或更多的交易以止损告终，交易将停止 `stop_duration` 分钟（或使用 `stop_duration_candles` 时的 K 线数，或使用 `unlock_at` 时设定的时间）。

这适用于所有交易对，除非 `only_per_pair` 设置为 true，此时它将仅分别查看每个交易对。

类似地，此保护机制默认会查看所有交易（多单和空单）。对于期货机器人，设置 `only_per_side` 将使机器人仅考虑单边交易，并且随后仅锁定该方向的交易。例如，允许在发生一系列多单止损后继续进行空单交易。

`required_profit` 将决定止损考虑所需的相对利润（或亏损）。通常不应设置此项，默认值为 0.0 - 这意味着所有导致亏损的止损都将触发锁定。

下面的示例在过去 24 根 K 线内发生 4 次止损后，将所有交易对的交易停止 4 根 K 线。

``` python
@property
def protections(self):
    return [
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 24,
            "trade_limit": 4,
            "stop_duration_candles": 4,
            "required_profit": 0.0,
            "only_per_pair": False,
            "only_per_side": False
        }
    ]
```

!!! Note
    `StoplossGuard` 考虑所有结果为 `"stop_loss"`、`"stoploss_on_exchange"` 和 `"trailing_stop_loss"` 且最终利润为负的交易。
    `trade_limit` 和 `lookback_period` 需要针对您的策略进行调整。

#### 最大回撤保护 (MaxDrawdown)

`MaxDrawdown` 利用 `lookback_period` 分钟（或使用 `lookback_period_candles` 时对应的 K 线数）内的所有交易来确定最大回撤。如果回撤达到 `max_allowed_drawdown`，交易将在最后一次交易后停止 `stop_duration` 分钟（或使用 `stop_duration_candles` 时的 K 线数）—— 假设机器人需要一些时间让市场恢复。

以下示例在过去 48 根 K 线内，考虑所有交易对（最少 `trade_limit` 笔交易）的最大回撤 > 20% 时，停止交易 12 根 K 线。如果需要，可以使用 `lookback_period` 和/或 `stop_duration`。

``` python
@property
def protections(self):
    return  [
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 48,
            "trade_limit": 20,
            "stop_duration_candles": 12,
            "max_allowed_drawdown": 0.2
        },
    ]
```

#### 低利润交易对保护 (Low Profit Pairs)

`LowProfitPairs` 使用 `lookback_period` 分钟（或使用 `lookback_period_candles` 时对应的 K 线数）内某个交易对的所有交易来确定整体利润率。
如果该比率低于 `required_profit`，该交易对将被锁定 `stop_duration` 分钟（或使用 `stop_duration_candles` 时的 K 线数，或直到使用 `unlock_at` 设定的时间）。

对于期货机器人，设置 `only_per_side` 将使机器人仅考虑单边交易，并且随后仅锁定该方向的交易。例如，允许在发生一系列多单亏损后继续进行空单交易。

以下示例中，如果某个交易对在过去 6 根 K 线内没有达到 2% 的所需利润（且最少包含 2 笔交易），则将停止该交易对 60 分钟。

``` python
@property
def protections(self):
    return [
        {
            "method": "LowProfitPairs",
            "lookback_period_candles": 6,
            "trade_limit": 2,
            "stop_duration": 60,
            "required_profit": 0.02,
            "only_per_pair": False,
        }
    ]
```

#### 冷却期 (Cooldown Period)

`CooldownPeriod` 在平仓后将交易对锁定 `stop_duration` 分钟（或使用 `stop_duration_candles` 时的 K 线数，或直到使用 `unlock_at` 设定的时间），从而避免在该交易对平仓后 `stop_duration` 分钟内重新入场。

以下示例在平仓后将交易对交易停止 2 根 K 线，让该交易对“冷却”。

``` python
@property
def protections(self):
    return  [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 2
        }
    ]
```

!!! Note
    此保护机制仅在交易对级别起作用，绝不会全局锁定所有交易对。
    此保护机制不考虑 `lookback_period`，因为它仅查看最近的一笔交易。

### 保护机制完整示例

所有保护机制都可以随意组合，也可以使用不同的参数，为表现不佳的交易对建立一道不断升级的防护墙。
所有保护机制按照定义的顺序进行评估。

以下示例假设时间框架为 1 小时：

* 在卖出后将每个交易对额外锁定 5 根 K 线 (`CooldownPeriod`)，给其他交易对成交的机会。
* 如果过去 2 天 (`48 * 1h K线`) 发生了 20 笔交易，且导致最大回撤超过 20%，则停止交易 4 小时 (`4 * 1h K线`) (`MaxDrawdown`)。
* 如果 1 天 (`24 * 1h K线`) 内所有交易对发生超过 4 次止损，则停止交易 (`StoplossGuard`)。
* 锁定过去 6 小时 (`6 * 1h K线`) 内发生了 2 笔交易且合并利润率低于 0.02 (<2%) 的所有交易对 (`LowProfitPairs`)。
* 将过去 24 小时 (`24 * 1h K线`) 内利润低于 0.01 (<1%) 且最少发生 4 笔交易的所有交易对锁定 2 根 K 线。

``` python
from freqtrade.strategy import IStrategy

class AwesomeStrategy(IStrategy):
    timeframe = '1h'
    
    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 5
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 20,
                "stop_duration_candles": 4,
                "max_allowed_drawdown": 0.2
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 2,
                "only_per_pair": False
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 6,
                "trade_limit": 2,
                "stop_duration_candles": 60,
                "required_profit": 0.02
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 2,
                "required_profit": 0.01
            }
        ]
    # ...
```
