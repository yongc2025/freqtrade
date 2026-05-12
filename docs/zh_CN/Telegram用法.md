# Telegram 用法 (Telegram usage)

## 设置您的 Telegram 机器人

下面我们解释如何创建您的 Telegram 机器人，以及如何获取您的 Telegram 用户 ID。

### 1. 创建您的 Telegram 机器人

开始与 [Telegram BotFather](https://telegram.me/BotFather) 聊天。

发送消息 `/newbot`。

*BotFather 的回应：*

> Alright, a new bot. How are we going to call it? Please choose a name for your bot. (好的，一个新的机器人。我们该怎么称呼它？请为您的机器人选择一个名字。)

选择您的机器人的公开名称（例如：`Freqtrade 机器人`）。

*BotFather 的回应：*

> Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot. (很好。现在让我们为您的机器人选择一个用户名。它必须以 `bot` 结尾。例如：TetrisBot 或 tetris_bot。)

选择您的机器人的 ID 名称并发送给 BotFather（例如：`My_own_freqtrade_bot`）。

*BotFather 的回应：*

> Done! Congratulations on your new bot. You will find it at `t.me/yourbots_name_bot`. You can now add a description, about section and profile picture for your bot, see /help for a list of commands. By the way, when you've finished creating your cool bot, ping our Bot Support if you want a better username for it. Just make sure the bot is fully operational before you do this. (完成了！恭喜您获得新的机器人。您可以在 `t.me/yourbots_name_bot` 找到它。您现在可以为机器人添加描述、关于部分和个人资料图片，请参阅 /help 获取命令列表。顺便说一句，当您完成酷炫机器人的创建后，如果您想要更好的用户名，请联系我们的机器人支持。只需在执行此操作前确保机器人能完全正常运行。)

> Use this token to access the HTTP API: `22222222:APITOKEN` (使用此令牌访问 HTTP API：`22222222:APITOKEN`)

> For a description of the Bot API, see this page: https://core.telegram.org/bots/api (有关机器人 API 的说明，请参阅此页面：https://core.telegram.org/bots/api)

复制 API 令牌（在上面的例子中为 `22222222:APITOKEN`）并将其用于配置参数 `token`。

别忘了通过点击 `/START` 按钮开始与您的机器人对话。

### 2. Telegram 用户 ID (user_id)

#### 获取您的用户 ID

与 [userinfobot](https://telegram.me/userinfobot) 对话。

获取您的 "Id"，您将把它用于配置参数 `chat_id`。

#### 使用群组 ID

要获取群组 ID，您可以将机器人添加到群组中，启动 freqtrade，然后发出 `/tg_info` 命令。
这将向您返回群组 ID，而无需使用某些随机机器人。
虽然仍需要 "chat_id"，但在执行此命令时不需要将其设置为特定的群组 ID。

响应还将包含 "topic_id"（如果必要）—— 两者都以可以直接复制/粘贴到配置中的格式提供。

``` json
 {
    "enabled": true,
    "token": "********",
    "chat_id": "-1001332619709",
    "topic_id": "122"
}
```

对于 Freqtrade 配置，您可以将完整的值（包括 `-`）作为字符串使用：

```json
   "chat_id": "-1001332619709"
```

!!! Warning "使用 Telegram 群组"
    使用 Telegram 群组时，您正在赋予群组中的每个成员访问您的 freqtrade 机器人以及通过 Telegram 执行所有可能命令的权限。请确保您可以信任群组中的每个人，以避免不愉快的意外。

##### 群组话题 ID (Group Topic ID)

要在群组中使用特定话题 (Topic)，您可以在配置中使用 `topic_id` 参数。这将允许您在群组的特定话题中使用机器人。
如果不设置，在启用了话题的群组聊天中，机器人将始终响应群组中的通用频道 (General channel)。

```json
   "chat_id": "-1001332619709",
   "topic_id": "3"
```

与群组 ID 类似 —— 您可以从话题/主题 (Topic/Thread) 中使用 `/tg_info` 来获取正确的话题 ID。

#### 授权用户 (Authorized users)

对于群组，限制谁可以向机器人发送命令是很有用的。

如果 `"authorized_users": []` 存在且为空，则不允许任何用户控制机器人。
在下面的例子中，只有 ID 为 "1234567" 的用户被允许控制机器人 —— 所有其他用户将只能接收消息。

```json
   "chat_id": "-1001332619709",
   "topic_id": "3",
   "authorized_users": ["1234567"]
```

## 控制 Telegram 通知 (Noise Control)

Freqtrade 提供了控制 Telegram 机器人详细程度的方法。
每个设置都有以下可能的值：

* `on` - 消息将被发送，并通知用户。
* `silent` - 消息将被发送，通知将没有声音/振动。
* `off` - 完全跳过发送该类型的消息。

显示不同设置的配置示例：

``` json
"telegram": {
    "enabled": true,
    "token": "your_telegram_token",
    "chat_id": "your_telegram_chat_id",
    "allow_custom_messages": true,
    "notification_settings": {
        "status": "silent",
        "warning": "on",
        "startup": "off",
        "entry": "silent",
        "entry_fill": "on",
        "entry_cancel": "silent",
        "exit": {
            "roi": "silent",
            "emergency_exit": "on",
            "force_exit": "on",
            "exit_signal": "silent",
            "trailing_stop_loss": "on",
            "stop_loss": "on",
            "stoploss_on_exchange": "on",
            "custom_exit": "silent",  // 未指定退出原因的 custom_exit
            "partial_exit": "on",
            // "custom_exit_message": "silent",  // 禁用单独的自定义退出原因
            "*": "off"  // 禁用所有其他退出原因
        },
        // "exit": "off",  // 禁用所有退出消息的简化配置
        "exit_cancel": "on",
        "exit_fill": "off",
        "protection_trigger": "off",
        "protection_trigger_global": "on",
        "strategy_msg": "off",
        "show_candle": "off"
    },
    "reload": true,
    "balance_dust_level": 0.01
},
```

* `entry` (开仓) 通知在订单发出时发送，而 `entry_fill` (开仓成交) 通知在订单在交易所成交时发送。
* `exit` (平仓) 通知在订单发出时发送，而 `exit_fill` (平仓成交) 通知在订单在交易所成交时发送。
    平仓消息（`exit` 和 `exit_fill`）可以在具体的退出原因级别进一步控制，以具体的退出原因为键 (key)。所有退出原因的默认值为 `on` —— 但也可以通过特殊的 `*` 键进行配置 —— 它将作为所有未明确定义的退出原因的通配符。
* `*_fill` 通知默认关闭，必须显式启用。
* `protection_trigger` 通知在保护机制触发时发送，而 `protection_trigger_global` 通知在全局保护机制触发时发送。
* `strategy_msg` - 接收来自策略的通知，由策略通过 `self.dp.send_msg()` 发送 [更多详情](策略自定义.md#send-notification)。
* `show_candle` - 在开仓/平仓消息中显示 K 线值。唯一可能的值是 `"ohlc"` 或 `"off"`。
* `balance_dust_level` 定义 `/balance` 命令将其视为“微尘 (dust)”的数额 —— 余额低于此值的货币将不被显示。
* `allow_custom_messages` 完全禁用策略消息。
* `reload` 允许您在选定的消息上禁用重载按钮。

## 创建自定义键盘 (命令快捷按钮)

Telegram 允许我们创建带有命令按钮的自定义键盘。
默认的自定义键盘如下所示。

```python
[
    ["/daily", "/profit", "/balance"], # 第 1 行，3 个命令
    ["/status", "/status table", "/performance"], # 第 2 行，3 个命令
    ["/count", "/start", "/stop", "/help"] # 第 3 行，4 个命令
]
```

### 用法

您可以在 `config.json` 中创建自己的键盘：

``` json
"telegram": {
      "enabled": true,
      "token": "your_telegram_token",
      "chat_id": "your_telegram_chat_id",
      "keyboard": [
          ["/daily", "/stats", "/balance", "/profit"],
          ["/status table", "/performance"],
          ["/reload_config", "/count", "/logs"]
      ]
   },
```

!!! Note "受支持的命令"
    仅允许使用以下命令。不支持命令参数！

    `/start`, `/pause`, `/stop`, `/status`, `/status table`, `/trades`, `/profit`, `/performance`, `/daily`, `/stats`, `/count`, `/locks`, `/balance`, `/stopentry`, `/reload_config`, `/show_config`, `/logs`, `/whitelist`, `/blacklist`, `/help`, `/version`, `/marketdir`

## Telegram 命令

默认情况下，Telegram 机器人会显示预定义的命令。有些命令只能通过发送给机器人来使用。下表列出了官方命令。您可以随时通过 `/help` 寻求帮助。

| 命令 | 描述 |
|----------|-------------|
| **系统命令** | |
| `/start` | 启动交易机器人 |
| `/pause \| /stopentry \| /stopbuy` | 暂停交易。根据规则从容处理开仓交易。不进入新头寸。 |
| `/stop` | 停止交易机器人 |
| `/reload_config` | 重新加载配置文件 |
| `/show_config` | 显示当前配置的一部分，以及与运行相关的设置 |
| `/logs [limit]` | 显示最后的日志消息。 |
| `/help` | 显示帮助消息 |
| `/version` | 显示版本信息 |
| **状态** | |
| `/status` | 列出所有开仓交易 |
| `/status <trade_id>` | 列出一个或多个特定的交易。多个 <trade_id> 之间用空格分隔。 |
| `/status table` | 以表格格式列出所有开仓交易。待处理的买单用星号 (*) 标记，待处理的卖单用双星号 (**) 标记 |
| `/order <trade_id>` | 列出一个或多个特定交易的订单。多个 <trade_id> 之间用空格分隔。 |
| `/trades [limit]` | 以表格格式列出最近关闭的所有交易。 |
| `/count` | 显示已使用和可用的交易数量 |
| `/locks` | 显示当前锁定的交易对。 |
| `/unlock <pair or lock_id>` | 移除该交易对（或该锁定 ID）的锁定。 |
| `/marketdir [long \| short \| even \| none]` | 更新代表当前市场方向的用户管理变量。如果没有提供方向，则将显示当前设置的方向。 |
| `/list_custom_data <trade_id> [key]` | 列出交易 ID 和键组合的 custom_data。如果没有提供键，它将列出为该交易 ID 找到的所有键值对。 |
| **修改交易状态** | |
| `/forceexit <trade_id> \| /fx <tradeid>` | 立即退出给定的交易（忽略 `minimum_roi`）。 |
| `/forceexit all \| /fx all` | 立即退出所有开仓交易（忽略 `minimum_roi`）。 |
| `/fx` | `/forceexit` 的别名 |
| `/forcelong <pair> [rate]` | 立即买入给定的交易对。汇率 (rate) 是可选的，且仅适用于限价单。(`force_entry_enable` 必须设置为 True) |
| `/forceshort <pair> [rate]` | 立即对给定的交易对做空。汇率 (rate) 是可选的，且仅适用于限价单。这仅适用于非现货市场。(`force_entry_enable` 必须设置为 True) |
| `/delete <trade_id>` | 从数据库中删除特定交易。尝试关闭挂单。需要手动在交易所处理此交易。 |
| `/reload_trade <trade_id>` | 从交易所重新加载交易。仅在实盘中有效，可能有助于恢复在交易所手动卖出的交易。 |
| `/cancel_open_order <trade_id> \| /coo <trade_id>` | 取消一个交易的待处理订单。 |
| **指标** | |
| `/profit [<n>]` | 显示已平仓交易的盈亏摘要，以及过去 n 天您的表现统计数据（默认为所有交易） |
| `/profit_[long\|short] [<n>]` | 显示单方向已平仓交易的盈亏摘要，以及过去 n 天您的表现统计数据（默认为所有交易） |
| `/performance` | 显示按交易对分组的每笔已完成交易的表现 |
| `/balance` | 显示机器人管理的每种货币余额 |
| `/balance full` | 显示每个账户的货币余额 |
| `/daily <n>` | 显示过去 n 天每天的利润或亏损（n 默认为 7） |
| `/weekly <n>` | 显示过去 n 周每周的利润或亏损（n 默认为 8） |
| `/monthly <n>` | 显示过去 n 个月每月的利润或亏损（n 默认为 6） |
| `/stats` | 显示按退出原因划分的胜/负，以及买入和卖出的平均持仓时间 |
| `/exits` | 显示按退出原因划分的胜/负，以及平均持仓时间 |
| `/entries` | 显示按退出原因划分的胜/负，以及平均持仓时间 |
| `/whitelist [sorted] [baseonly]` | 显示当前白名单。可选按字母顺序显示和/或仅显示每个配对的基础货币。 |
| `/blacklist [pair]` | 显示当前黑名单，或将一个交易对添加到黑名单。 |

## Telegram 命令实战

以下是您每个命令将接收到的 Telegram 消息示例。

### /start

> **状态 (Status):** `running`

### /pause | /stopentry | /stopbuy

> **状态 (Status):** `paused, no more entries will occur from now. Run /start to enable entries. (已暂停，从现在起不会再有入场。运行 /start 以启用入场。)`

通过将状态更改为 `paused` 来防止机器人开启新交易。
开仓交易将继续按照其常规规则（ROI/平仓信号、止损等）进行管理。
请注意，仓位调整仍然有效，但仅限于平仓侧 —— 这意味着当机器人处于 `paused` 状态时，它只能减少开仓交易的仓位规模。

之后，给机器人一些时间来关闭开仓交易（可以通过 `/status table` 检查）。
一旦所有头寸关闭，运行 `/stop` 以完全停止机器人。

使用 `/start` 将机器人恢复到 `running` 状态，允许其开启新头寸。

!!! Warning "警告"
    pause/stopentry 信号仅在机器人运行时有效，且不会被持久化，因此重启机器人将导致此信号重置。

### /stop

> `Stopping trader ... (正在停止交易...)`
> **状态 (Status):** `stopped`

### /status

对于每个开仓交易，机器人将发送以下消息。
入场标签 (Enter Tag) 可通过策略配置。

> **交易 ID (Trade ID):** `123` `(自 1 天前起)`  
> **当前交易对 (Current Pair):** CVC/BTC  
> **方向 (Direction):** Long  
> **杠杆 (Leverage):** 1.0  
> **数量 (Amount):** `26.64180098`  
> **入场标签 (Enter Tag):** Awesome Long Signal  
> **开仓价格 (Open Rate):** `0.00007489`  
> **当前价格 (Current Rate):** `0.00007489`  
> **未实现利润 (Unrealized Profit):** `12.95%`  
> **止损 (Stoploss):** `0.00007389 (-0.02%)`  

### /status table

以表格格式返回所有开仓交易的状态。

```
ID L/S    Pair     Since   Profit
----    --------  -------  --------
  67 L   SC/BTC    1 d      13.33%
 123 S   CVC/BTC   1 h      12.95%
```

### /count

返回已使用和可用的交易数量。

```
current    max
---------  -----
     2     10
```

### /profit

也可作为 `/profit_long` 和 `/profit_short` 使用，以仅显示多单或空单的利润。

返回您的盈亏和表现摘要。

> **ROI:** 已平仓交易 (Close trades)  
>   ∙ `0.00485701 BTC (2.2%) (15.2 Σ%)`  
>   ∙ `62.968 USD`  
> **ROI:** 所有交易 (All trades)  
>   ∙ `0.00255280 BTC (1.5%) (6.43 Σ%)`  
>   ∙ `33.095 EUR`  
>  
> **总交易数量 (Total Trade Count):** `138`  
> **机器人启动时间 (Bot started):** `2022-07-11 18:40:44`  
> **首次交易开启:** `3 天前`  
> **最近交易开启:** `2 分钟前`  
> **平均持续时间 (Avg. Duration):** `2:33:45`  
> **表现最佳:** `PAY/BTC: 50.23%`  
> **交易额 (Trading volume):** `0.5 BTC`  
> **利润因子 (Profit factor):** `1.04`  
> **盈 / 亏:** `102 / 36`  
> **胜率 (Winrate):** `73.91%`  
> **期望值 (比率) (Expectancy (Ratio)):** `4.87 (1.66)`  
> **最大回撤 (Max Drawdown):** `9.23% (0.01255 BTC)`  

`1.2%` 的相对利润是每笔交易的平均利润。
`15.2 Σ%` 的相对利润基于起始资金 —— 所以在这个例子中，起始资金是 `0.00485701 * 1.152 = 0.00738 BTC`。
**起始资金 (Starting capital)** 要么取自 `available_capital` 设置，要么通过使用当前钱包规模 - 利润来计算。
**利润因子 (Profit Factor)** 计算为 毛利 / 毛损 —— 且应作为策略的整体指标。
**期望值 (Expectancy)** 对应于每单位风险资金的平均回报，即胜率和风险回报比（获利交易的平均增益与亏损交易的平均损失之比）。
**期望比率 (Expectancy Ratio)** 是基于所有过去交易表现的后续交易的预期损益。
**最大回撤 (Max drawdown)** 对应于回测指标 `绝对回撤 (账户) (Absolute Drawdown (Account))` —— 计算公式为 `(绝对回撤) / (历史最高值 + 初始余额)`。
**机器人启动日期 (Bot started date)** 指的是机器人首次启动的日期。对于较早的机器人，这将默认为第一笔交易的开启日期。

### /forceexit <trade_id>

> **BINANCE:** Exiting BTC/LTC with limit `0.01650000 (profit: ~-4.07%, -0.00008168)`

!!! Tip "技巧"
    您可以通过不带参数地调用 `/forceexit` 来获取所有开仓交易的列表，这将显示一组用于简单平仓的按钮。
    此命令有一个别名 `/fx` —— 它具有相同的功能，但在“紧急”情况下输入速度更快。

### /forcelong <pair> [rate] | /forceshort <pair> [rate]

对于做多也支持 `/forcebuy <pair> [rate]`，但应被视为已过时。

> **BINANCE:** Long ETH/BTC with limit `0.03400000` (`1.000000 ETH`, `225.290 USD`)

省略交易对将开启一个查询，询问要交易的交易对（基于当前白名单）。
通过 `/forcelong` 创建的交易将带有 `force_entry` 的买入标签。

![Telegram 强制买入截图](assets/telegram_forcebuy.png)

请注意，要使此功能生效，`force_entry_enable` 需要设置为 true。

[更多详情](配置.md#understand-force_entry_enable)

### /performance

返回机器人已卖出的每种加密货币的表现。
> Performance:  
> 1. `RCN/BTC 0.003 BTC (57.77%) (1)`  
> 2. `PAY/BTC 0.0012 BTC (56.91%) (1)`  
> 3. `VIB/BTC 0.0011 BTC (47.07%) (1)`  
> 4. `SALT/BTC 0.0010 BTC (30.24%) (1)`  
> 5. `STORJ/BTC 0.0009 BTC (27.24%) (1)`  
> ...  

相对表现是相对于该货币的总投资额计算的，汇总了该货币的所有已成交入场。

### /balance

返回您在交易所拥有的所有加密货币的余额。

> **货币:** BTC  
> **可用:** 3.05890234  
> **余额:** 3.05890234  
> **挂单中:** 0.0  
>
> **货币:** CVC  
> **可用:** 86.64180098  
> **余额:** 86.64180098  
> **挂单中:** 0.0  

### /daily <n>

默认情况下，`/daily` 将返回过去 7 天的结果。以下为 `/daily 3` 的示例：

> **过去 3 天的每日利润：**

```
日期 (数量)     USDT          USD         利润 %
--------------  ------------  ----------  ----------
2022-06-11 (1)  -0.746 USDT   -0.75 USD   -0.08%
2022-06-10 (0)  0 USDT        0.00 USD    0.00%
2022-06-09 (5)  20 USDT       20.10 USD   5.00%
```

### /weekly <n>

默认情况下，`/weekly` 将返回过去 8 周的结果，包括当前周。每周从周一开始。以下为 `/weekly 3` 的示例：

> **过去 3 周的每周利润（从周一开始）：**

```
周一 (数量)     利润 BTC        利润 USD     利润 %
-------------  --------------  ------------    ----------
2018-01-03 (5)  0.00224175 BTC  29,142 USD   4.98%
2017-12-27 (1)  0.00033131 BTC   4,307 USD   0.00%
2017-12-20 (4)  0.00269130 BTC  34.986 USD   5.12%
```

### /monthly <n>

默认情况下，`/monthly` 将返回过去 6 个月的结果，包括当前月。以下为 `/monthly 3` 的示例：

> **过去 3 个月的每月利润：**
```
月份 (数量)     利润 BTC        利润 USD      利润 %
-------------  --------------  ------------    ----------
2018-01 (20)    0.00224175 BTC  29,142 USD  4.98%
2017-12 (5)    0.00033131 BTC   4,307 USD   0.00%
2017-11 (10)    0.00269130 BTC  34.986 USD  5.10%
```

### /whitelist

显示当前白名单。

> Using whitelist `StaticPairList` with 22 pairs  
> `IOTA/BTC, NEO/BTC, TRX/BTC, VET/BTC, ADA/BTC, ETC/BTC, NCASH/BTC, DASH/BTC, XRP/BTC, XVG/BTC, EOS/BTC, LTC/BTC, OMG/BTC, BTG/BTC, LSK/BTC, ZEC/BTC, HOT/BTC, IOTX/BTC, XMR/BTC, AST/BTC, XLM/BTC, NANO/BTC`

### /blacklist [pair]

显示当前黑名单。
如果设置了 Pair (交易对)，则该交易对将被添加到黑名单中。
也支持多个交易对，用空格分隔。
使用 `/reload_config` 来重置黑名单。

> Using blacklist `StaticPairList` with 2 pairs  
>`DODGE/BTC`, `HOT/BTC`.  

### /version

> **版本:** `0.14.3`

### /marketdir

如果提供了市场方向，该命令将更新代表当前市场方向的用户管理变量。
此变量在机器人启动时未设置为任何有效的市场方向，必须由用户设置。以下示例为 `/marketdir long`：

```
Successfully updated marketdirection from none to long.
```

如果没有提供市场方向，该命令将输出当前设置的市场方向。以下示例为 `/marketdir`：

```
Currently set marketdirection: even
```

您可以通过 `self.market_direction` 在策略中使用市场方向。

!!! Warning "机器人重启"
    请注意，市场方向不会被持久化，机器人重启/重新加载后将被重置。

!!! Danger "回测"
    由于此值/变量旨在在干跑/实盘交易中手动更改。
    使用 `market_direction` 的策略可能不会产生可靠、可重现的结果（对此变量的更改不会反映在回测中）。使用风险自担。
