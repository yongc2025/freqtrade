## 交易对列表与处理器 (Pairlists and Pairlist Handlers)

交易对列表处理器定义了机器人应交易的资产列表（pairlist）。它们在配置设置的 `pairlists` 部分中进行配置。

在配置中，您可以使用静态交易对列表（由 [`StaticPairList`](#静态交易对列表-static-pair-list) 处理器定义）和动态交易对列表（由 [`VolumePairList`](#成交量交易对列表-volume-pair-list) 和 [`PercentChangePairList`](#涨跌幅交易对列表-percent-change-pair-list) 处理器定义）。

此外，[`AgeFilter`](#agefilter)、[`DelistFilter`](#delistfilter)、[`PrecisionFilter`](#precisionfilter)、[`PriceFilter`](#pricefilter)、[`ShuffleFilter`](#shufflefilter)、[`SpreadFilter`](#spreadfilter) 和 [`VolatilityFilter`](#volatilityfilter) 作为交易对列表过滤器起作用，它们可以移除某些交易对和/或移动它们在列表中的位置。

如果使用了多个交易对列表处理器，它们会链式执行，所有处理器的组合形成了机器人用于交易和回测的最终列表。处理器按其配置的顺序执行。您可以定义 `StaticPairList`、`VolumePairList`、`ProducerPairList`、`RemotePairList`、`MarketCapPairList` 或 `PercentChangePairList` 作为起始处理器。

非活跃市场总是会从最终列表中移除。明确列入黑名单的交易对（配置设置 `pair_blacklist` 中的交易对）也总是会从最终列表中移除。

### 交易对黑名单

交易对黑名单（通过配置中的 `exchange.pair_blacklist` 配置）禁止特定交易对进行交易。
这可以简单地排除 `DOGE/BTC` —— 这将删除确切的这个对。

交易对黑名单还支持通配符（正则表达式风格）—— 因此 `BNB/.*` 将排除所有以 BNB 开头的交易对。
您也可以使用类似 `.*DOWN/BTC` 或 `.*UP/BTC` 的设置来排除杠杆通证（请检查您交易所的交易对命名约定！）。

### 可用的交易对列表处理器

* [`StaticPairList`](#静态交易对列表-static-pair-list)（默认，如果未另行配置）
* [`VolumePairList`](#成交量交易对列表-volume-pair-list)
* [`PercentChangePairList`](#涨跌幅交易对列表-percent-change-pair-list)
* [`ProducerPairList`](#producerpairlist)
* [`RemotePairList`](#remotepairlist)
* [`MarketCapPairList`](#marketcappairlist)
* [`AgeFilter`](#agefilter)
* [`DelistFilter`](#delistfilter)
* [`FullTradesFilter`](#fulltradesfilter)
* [`OffsetFilter`](#offsetfilter)
* [`PerformanceFilter`](#performancefilter)
* [`PrecisionFilter`](#precisionfilter)
* [`PriceFilter`](#pricefilter)
* [`ShuffleFilter`](#shufflefilter)
* [`SpreadFilter`](#spreadfilter)
* [`RangeStabilityFilter`](#rangestabilityfilter)
* [`VolatilityFilter`](#volatilityfilter)

!!! Tip "测试交易对列表"
    交易对列表配置可能非常棘手。最好使用处于 [Web 服务器模式](FreqUI界面.md#web-服务器模式) 的 FreqUI 或 [`test-pairlist`](实用工具.md#测试交易对列表) 实用工具子命令来快速测试您的配置。

#### 静态交易对列表 (Static Pair List)

默认情况下使用 `StaticPairList` 方法，它使用来自配置的静态定义的白名单。该列表还支持通配符（正则表达式风格）—— 因此 `.*/BTC` 将包含所有以 BTC 作为计价货币的交易对。

它使用来自 `exchange.pair_whitelist` 和 `exchange.pair_blacklist` 的配置。在下面的示例中，它将交易 BTC/USDT 和 ETH/USDT —— 并将阻止 BNB/USDT 交易。

两个 `pair_*list` 参数都支持正则表达式 —— 因此像 `.*/USDT` 这样的值将启用所有不在黑名单中的交易对。

```json
"exchange": {
    "name": "...",
    // ... 
    "pair_whitelist": [
        "BTC/USDT",
        "ETH/USDT",
        // ...
    ],
    "pair_blacklist": [
        "BNB/USDT",
        // ...
    ]
},
"pairlists": [
    {"method": "StaticPairList"}
],
```

默认情况下，仅允许当前启用的对。
要跳过针对活跃市场的验证，请在 `StaticPairList` 配置中设置 `"allow_inactive": true`。
这对于回测已过期的对（如季度现货市场）很有用。

当在“后续”位置（例如在 VolumePairlist 之后）使用时，`'pair_whitelist'` 中的所有对将被添加到列表的末尾。

#### 成交量交易对列表 (Volume Pair List)

`VolumePairList` 根据交易量对交易对进行排序/过滤。它根据 `sort_key`（只能是 `quoteVolume`）进行排序，选择前 `number_assets` 个交易对。

当在非首位的处理器链中使用时（在 StaticPairList 和其他过滤器之后），`VolumePairList` 考虑先前处理器的输出，并根据交易量添加其排序/选择。

当在处理器链的首位使用时，`pair_whitelist` 配置将被忽略。相反，`VolumePairList` 从交易所中具有匹配计价货币的所有可用市场中选择顶级资产。

`refresh_period` 设置允许定义刷新列表的时间间隔（以秒为单位）。默认为 1800 秒（30 分钟）。
`VolumePairList` 上的缓存 (`refresh_period`) 仅适用于生成列表。
作为过滤器实例（不在列表首位）将不应用任何缓存（在高级模式下，除了在 K 线持续期间缓存 K 线之外），并且将始终使用最新数据。

`VolumePairList` 默认基于 ccxt 库报告的来自交易所的 ticker 数据：

* `quoteVolume` 是过去 24 小时内交易（买入或卖出）的计价（结算）货币金额。

```json
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 20,
        "sort_key": "quoteVolume",
        "min_value": 0,
        "max_value": 8000000,
        "refresh_period": 1800
    }
],
```

您可以使用 `min_value` 定义最小成交量 —— 这将过滤掉在指定时间范围内成交量低于指定值的交易对。
除此之外，您还可以使用 `max_value` 定义最大成交量 —— 这将过滤掉成交量高于指定值的交易对。

##### VolumePairList 高级模式

`VolumePairList` 也可以在高级模式下运行，以在指定 K 线大小的给定时间范围内构建成交量。它利用交易所的历史 K 线数据，构建典型价格（通过 (最高价+最低价+收盘价)/3 计算）并将典型价格与每根 K 线成交量相乘。其总和就是给定范围内的 `quoteVolume`（成交量价值）。这允许不同的场景，当使用较大 K 线大小的较长范围时，成交量会更平滑；反之，当使用较小 K 线的小范围时，成交量会更灵敏。

为了方便，可以指定 `lookback_days`，这意味着将使用 1d（天）K 线进行回溯。在下面的示例中，将基于过去 7 天创建交易对列表：

```json
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 20,
        "sort_key": "quoteVolume",
        "min_value": 0,
        "refresh_period": 86400,
        "lookback_days": 7
    }
],
```

!!! Warning "回溯范围和刷新间隔"
    当结合使用 `lookback_days` 和 `lookback_timeframe` 时，`refresh_period` 不能小于以秒为单位的 K 线大小。因为这将导致对交易所 API 的不必要请求。

!!! Warning "使用回溯范围时的性能影响"
    如果在首位结合使用回溯，基于范围的成交量计算可能会耗费时间和资源，因为它会下载所有可交易对的 K 线。因此，强烈建议使用带有 `VolumeFilter` 的标准方法来缩小交易对列表，以便进行进一步的范围成交量计算。

??? Tip "不支持的交易所"
    在某些交易所（如 Gemini），常规的 VolumePairList 可能无法工作，因为其 API 原生不提供 24 小时成交量。可以通过使用 K 线数据来构建成交量来解决此问题。
    要大致模拟 24 小时成交量，您可以使用以下配置。
    请注意，这些列表每天仅刷新一次。

    ```json
    "pairlists": [
        {
            "method": "VolumePairList",
            "number_assets": 20,
            "sort_key": "quoteVolume",
            "min_value": 0,
            "refresh_period": 86400,
            "lookback_days": 1
        }
    ],
    ```

可以使用更复杂的方法，通过 `lookback_timeframe` 设置 K 线大小，并使用 `lookback_period` 指定 K 线数量。此示例将基于 1h K 线、3 天的滚动周期构建成交量：

```json
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 20,
        "sort_key": "quoteVolume",
        "min_value": 0,
        "refresh_period": 3600,
        "lookback_timeframe": "1h",
        "lookback_period": 72
    }
],
```

!!! Note
    `VolumePairList` 不支持回测模式。

#### 涨跌幅交易对列表 (Percent Change Pair List)

`PercentChangePairList` 根据过去 24 小时内或高级选项中定义的任何时间窗口内的价格变动百分比对交易对进行过滤和排序。这允许交易者专注于经历过显着价格变动（无论是正面还是负面）的资产。

**配置选项**

* `number_assets`：指定根据 24 小时百分比变动要选择的前几名资产数量。
* `min_value`：设置最小百分比变动阈值。百分比变动低于此值的交易对将被过滤掉。
* `max_value`：设置最大百分比变动阈值。百分比变动高于此值的交易对将被过滤掉。
* `sort_direction`：指定根据百分比变动对交易对进行排序的顺序。接受两个值：`asc` 为升序，`desc` 为降序。
* `refresh_period`：定义刷新列表的时间间隔（以秒为单位）。默认为 1800 秒（30 分钟）。
* `lookback_days`：回溯天数。选择 `lookback_days` 时，`lookback_timeframe` 默认为 1d（天）。
* `lookback_timeframe`：用于回溯期的时间框架。
* `lookback_period`：要回溯的周期数。

当 `PercentChangePairList` 在其他处理器之后使用时，它将对这些处理器的输出进行操作。如果它是首位处理器，它将从具有指定计价货币的所有可用市场中选择交易对。

`PercentChangePairList` 使用来自交易所的 ticker 数据（通过 ccxt 库提供）：
涨跌幅百分比计算为过去 24 小时内的价格变动。

??? Note "不支持的交易所"
    在某些交易所（如 HTX/火币），常规的 PercentChangePairList 可能无法工作，因为其 API 原生不提供 24 小时价格涨跌幅。可以通过使用 K 线数据来计算涨跌幅百分比来解决此问题。要大致模拟 24 小时涨跌幅，您可以使用以下配置。请注意，这些列表每天仅刷新一次。
    ```json
    "pairlists": [
        {
            "method": "PercentChangePairList",
            "number_assets": 20,
            "min_value": 0,
            "refresh_period": 86400,
            "lookback_days": 1
        }
    ],
    ```

**从 Ticker 读取的配置示例**

```json
"pairlists": [
    {
        "method": "PercentChangePairList",
        "number_assets": 15,
        "min_value": -10,
        "max_value": 50
    }
],
```

在此配置中：

1. 根据过去 24 小时内最高的价格涨跌幅选择前 15 个对。
2. 仅考虑涨跌幅在 -10% 到 50% 之间的交易对。

**从 K 线读取的配置示例**

```json
"pairlists": [
    {
        "method": "PercentChangePairList",
        "number_assets": 15,
        "sort_key": "percentage",
        "min_value": 0,
        "refresh_period": 3600,
        "lookback_timeframe": "1h",
        "lookback_period": 72
    }
],
```

此示例基于 1h K 线、3 天的滚动周期构建百分比变动列表，通过 `lookback_timeframe` 设置 K 线大小，并使用 `lookback_period` 指定 K 线数量。

价格涨跌幅百分比使用以下公式计算，该公式表示当前 K 线收盘价与前一 K 线收盘价之间的百分比差异（由指定的时间框架和回溯期定义）：

$$ Percent Change = (\frac{当前收盘价 - 之前收盘价}{之前收盘价}) * 100 $$

!!! Warning "回溯范围和刷新间隔"
    当结合使用 `lookback_days` 和 `lookback_timeframe` 时，`refresh_period` 不能小于以秒为单位的 K 线大小。因为这将导致对交易所 API 的不必要请求。

!!! Warning "使用回溯范围时的性能影响"
    如果在首位结合使用回溯，基于范围的涨跌幅百分比计算可能会耗费时间和资源，因为它会下载所有可交易对的 K 线。因此，强烈建议使用 `PercentChangePairList` 的标准方法来缩小交易对列表。

!!! Note "回测"
    `PercentChangePairList` 不支持回测模式。

#### ProducerPairList

使用 `ProducerPairList`，您可以重用来自[生产者 (Producer)](生产者-消费者模式.md)的交易对列表，而无需在每个消费者上显式定义列表。

需要[消费者模式 (Consumer mode)](生产者-消费者模式.md)才能使此列表生效。

该列表将针对当前交易所配置对活跃交易对进行检查，以避免尝试在无效市场上进行交易。

您可以使用可选参数 `number_assets` 限制列表的长度。使用 `"number_assets"=0` 或省略此键将导致重用对当前设置有效的所有生产者交易对。

```json
"pairlists": [
    {
        "method": "ProducerPairList",
        "number_assets": 5,
        "producer_name": "default",
    }
],
```

!!! Tip "组合交易对列表"
    此列表可以与所有其他交易对列表和过滤器结合使用，以进一步缩减列表，也可以作为已定义交易对基础上的“附加”列表。
    `ProducerPairList` 也可以连续使用多次，组合来自多个生产者的对。
    显然，在这样复杂的配置中，生产者可能无法提供所有对的数据，因此策略必须适应这种情况。

#### RemotePairList

它允许用户从远程服务器或 freqtrade 目录中本地存储的 json 文件获取交易对列表，从而实现交易对列表的动态更新和自定义。

RemotePairList 在配置设置的 `pairlists` 部分中定义。它使用以下配置选项：

```json
"pairlists": [
    {
        "method": "RemotePairList",
        "mode": "whitelist",
        "processing_mode": "filter",
        "pairlist_url": "https://example.com/pairlist",
        "number_assets": 10,
        "refresh_period": 1800,
        "keep_pairlist_on_failure": true,
        "read_timeout": 60,
        "bearer_token": "my-bearer-token",
        "save_to_file": "user_data/filename.json" 
    }
]
```

可选的 `mode` 选项指定此列表应作为 `blacklist`（黑名单）还是 `whitelist`（白名单）使用。默认值为 "whitelist"。

RemotePairList 选项中可选的 `processing_mode` 决定了如何处理检索到的列表。它可以有两个值："filter"（过滤）或 "append"（追加）。默认值为 "filter"。

在 "filter" 模式下，检索到的列表用作过滤器。仅包含同时存在于原始列表和检索到的列表中的对。其他对被过滤掉。

在 "append" 模式下，检索到的列表被添加到原始列表中。两份列表中的所有对都包含在最终列表中，不做任何过滤。

`pairlist_url` 选项指定了列表所在的远程服务器 URL，或本地路径（如果前面带有 `file:///`）。这允许用户使用远程服务器或本地文件作为交易对列表的来源。

如果提供了有效的文件名，`save_to_file` 选项会将处理后的列表以 JSON 格式保存到该文件中。此选项是可选的，默认情况下，列表不会保存到文件中。

??? Example "多机器人共用交易对列表示例"

    可以使用 `save_to_file` 在 Bot1 中保存列表：

    ```json
    "pairlists": [
        {
            "method": "RemotePairList",
            "mode": "whitelist",
            "pairlist_url": "https://example.com/pairlist",
            "number_assets": 10,
            "refresh_period": 1800,
            "keep_pairlist_on_failure": true,
            "read_timeout": 60,
            "save_to_file": "user_data/filename.json" 
        }
    ]
    ```

    保存的列表文件可以由 Bot2 或任何其他具有以下配置的机器人加载：

    ```json
    "pairlists": [
        {
            "method": "RemotePairList",
            "mode": "whitelist",
            "pairlist_url": "file:///user_data/filename.json",
            "number_assets": 10,
            "refresh_period": 10,
            "keep_pairlist_on_failure": true,
        }
    ]
    ```    

用户有责任提供返回具有以下结构的 JSON 对象的服务器或本地文件：

```json
{
    "pairs": ["XRP/USDT", "ETH/USDT", "LTC/USDT"],
    "refresh_period": 1800
}
```

`pairs` 属性应包含一个由机器人使用的交易对字符串列表。`refresh_period` 属性是可选的，指定在刷新之前应缓存列表的秒数。

可选的 `keep_pairlist_on_failure` 指定如果远程服务器不可达或返回错误，是否应使用之前收到的列表。默认值为 true。

可选的 `read_timeout` 指定等待远程源响应的最大时间（以秒为单位）。默认值为 60。

可选的 `bearer_token` 将包含在请求的 Authorization Header 中。

!!! Note
    如果发生服务器错误，且 `keep_pairlist_on_failure` 设置为 true，则保留最后一次接收到的列表；如果设置为 false，则返回一个空列表。

#### MarketCapPairList

`MarketCapPairList` 根据 CoinGecko 提供的市值 (Market Cap) 排名对交易对进行排序/过滤。如果在白名单 `mode` 下使用，返回的列表将根据市值排名进行排序。

```json
"pairlists": [
    {
        "method": "MarketCapPairList",
        "number_assets": 20,
        "max_rank": 50,
        "refresh_period": 86400,
        "mode": "whitelist",
        "categories": ["layer-1"]
    }
]
```

如果在白名单 `mode`（模式）下使用，`number_assets` 定义返回列表的最大数量。在黑名单 `mode` 下，此设置将被忽略。

`max_rank` 将决定创建/过滤列表时使用的最高排名。预计顶级 `max_rank` 市值中的某些币种不会包含在最终列表中，因为并非所有币种在您喜欢的市场/计价/交易所组合中都有活跃的交易对。
虽然支持使用大于 250 的 `max_rank`，但并不推荐，因为它会导致对 CoinGecko 的多次 API 调用，从而可能导致速率限制问题。

`refresh_period` 设置定义了刷新市值排名数据的时间间隔（以秒为单位）。默认为 86,400 秒（1 天）。缓存 (`refresh_period`) 同时适用于生成列表（在列表首位时）和过滤实例（不在列表首位时）。

`mode` 设置定义插件是过滤掉（白名单 `mode`）还是过滤进（黑名单 `mode`）顶级市值排名的币种。默认情况下，插件处于白名单模式。

`categories` 设置指定从中选择币种的 [CoinGecko 类别](https://www.coingecko.com/en/categories)。默认为空列表 `[]`，表示不应用类别过滤。
如果选择了不正确的类别字符串，插件将打印 CoinGecko 提供的可用类别并失败。类别应该是类别的 ID，例如，对于 `https://www.coingecko.com/en/categories/layer-1`，类别 ID 将是 `layer-1`。您可以传递多个类别，例如 `["layer-1", "meme-token"]`。

诸如 1000PEPE/USDT 或 KPEPE/USDT:USDT 之类的币种会以尽力而为的方式进行检测，并使用前缀 `1000` 和 `K` 来识别它们。

!!! Warning "多个类别"
    每个添加的类别对应一次对 CoinGecko 的 API 调用。添加的类别越多，生成交易对列表所需的时间就越长，并可能导致速率限制问题。

!!! Danger "CoinGecko 中的重复符号"
    CoinGecko 经常有重复的符号，即同一个符号由于重名被用于不同的币种。Freqtrade 将按原样使用符号，并在交易所中搜索它。如果符号存在，它将被使用。但是，Freqtrade 不会检查该符号是否为 CoinGecko 所指的“预期”符号。这有时会导致意想不到的结果，特别是在低成交量的币种或模因币 (meme coin) 类别中。

#### AgeFilter

移除在交易所上市时间少于 `min_days_listed` 天（默认为 `10`）或超过 `max_days_listed` 天（默认 `None` 表示无穷大）的对。

当某种货币首次在交易所上市时，在价格发现的前几天通常会经历巨大的跌幅和波动。机器人经常会在价格停止下跌之前被诱进。

此过滤器允许 Freqtrade 忽略上市时间短于 `min_days_listed` 天或早于 `max_days_listed` 天上市的对。

#### DelistFilter

移除将在未来最大 `max_days_from_now` 天内下架的交易对（默认为 `0`，即移除所有未来将下架的对，无论距离现在多久）。目前此过滤器仅支持以下交易所：

!!! Note "可用交易所"
    下架过滤器在 Bybit 期货, Bitget 期货和 Binance（币安）上可用。其中 Binance 期货适用于模拟和实盘模式，而 Binance 现货仅限于实盘模式（由于技术原因）。

!!! Warning "回测"
    `DelistFilter` 不支持回测模式。

#### FullTradesFilter

当交易槽位已满时（当配置中的 `max_open_trades` 未设置为 `-1` 时），将白名单缩小为仅包含正在交易的对。

当交易槽位已满时，不需要计算其余对的指标（信息性对除外），因为无法开启新交易。通过将白名单缩小到仅包含正在交易的对，可以提高计算速度并降低 CPU 使用率。当有交易槽位闲置（某笔交易已关闭或配置中的 `max_open_trades` 值增加）时，白名单将恢复为正常状态。

当使用多个过滤器时，建议将此过滤器放在紧邻主处理器的第二位，这样在交易槽位已满时，机器人就不必下载其余过滤器所需的数据。

!!! Warning "回测"
    `FullTradesFilter` 不支持回测模式。

#### OffsetFilter

通过给定的 `offset`（偏移量）对输入的列表进行偏移。

作为一个示例，它可以与 `VolumeFilter` 结合使用以移除交易量前 X 的对。或者将较大的交易对列表拆分到两个机器人实例中。

示例：从列表中移除前 10 个对，并取接下来的 20 个（即取初始列表中的第 10-30 项）：

```json
"pairlists": [
    // ...
    {
        "method": "OffsetFilter",
        "offset": 10,
        "number_assets": 20
    }
],
```

!!! Warning
    当 `OffsetFilter` 结合 `VolumeFilter` 将大列表拆分给多个机器人时，由于 `VolumeFilter` 的刷新间隔略有不同，不能保证交易对不会重叠。

!!! Note
    如果偏移量大于输入列表的总长度，将产生一个空的列表。

#### PerformanceFilter

按过去交易绩效对交易对进行排序，如下所示：

1. 正绩效。
2. 尚未进行已平仓交易。
3. 负绩效。

交易次数作为平局决胜因素。

可以使用 `minutes` 参数，仅考虑过去 X 分钟内的绩效（滚动窗口）。
如果不定义此参数（或将其设置为 0），将使用历史累计绩效。

可选的 `min_profit`（比率 -> 设置为 `0.01` 对应 1%）参数定义了要考虑的对必须具有的最低利润。
低于此水平的对将被过滤掉。
强烈建议不要在不使用 `minutes` 的情况下使用此参数，因为这可能导致列表变空且无法恢复。

```json
"pairlists": [
    // ...
    {
        "method": "PerformanceFilter",
        "minutes": 1440,  // 滚动 24h
        "min_profit": 0.01  // 最小利润 1%
    }
],
```

由于此过滤器使用了机器人的过去绩效，它会有一段启动期 —— 并且只有在机器人数据库中已有数百笔交易后才应使用。

!!! Warning "回测"
    `PerformanceFilter` 不支持回测模式。

#### PrecisionFilter

过滤低价值币种，这些币种通常不允许设置止损。

即如果止损价百分之一或更多的方差是由交易所的舍入精度引起的，则对应的交易对将被列入黑名单，即 `rounded(stop_price) <= rounded(stop_price * 0.99)`。此设置的目的是避免选择价格非常接近其最低交易边界的币种，因为这种币种不允许设置适当的止损。

!!! Tip "PrecisionFilter 对于期货交易没有意义"
    上述情况不适用于空单。对于多单，理论上仓位会先被爆仓。

!!! Warning "回测"
    `PrecisionFilter` 在使用多种策略的回测模式下不受支持。

#### PriceFilter

`PriceFilter` 允许按价格过滤交易对。目前支持以下价格过滤器：

* `min_price`
* `max_price`
* `max_value`
* `low_price_ratio`

`min_price` 设置移除价格低于指定价格的对。如果您想避免交易价格极低的对，这会非常有用。
此选项默认禁用，仅在设置为 > 0 时生效。

`max_price` 设置移除价格高于指定价格的对。如果您只想交易低价对，这会非常有用。
此选项默认禁用，仅在设置为 > 0 时生效。

`max_value` 设置移除最小价值变化高于指定值的对。
这在交易所限制不平衡时非常有用。例如，如果步长 step-size = 1（因此您只能购买 1 个或 2 个或 3 个币，但不能购买 1.1 个）—— 且由于该币自上次限额调整以来大幅上涨导致价格相当高（如 20$）。
结果如上所述，您只能以 20\$ 或 40\$ 的金额购买 —— 而不能以 25\$ 购买。
在从接收货币中扣除手续费的交易所（如币安）上 —— 这可能导致高价值币种/金额无法卖出，因为数量略低于限额。

`low_price_ratio` 设置会移除价格上涨 1 个价格单位 (pip) 高于 `low_price_ratio` 比率的对。
此选项默认禁用，仅在设置为 > 0 时生效。

对于 `PriceFilter`，必须至少应用其 `min_price`、`max_price` 或 `low_price_ratio` 设置中的一个。

计算示例：

SHITCOIN/BTC 的最小价格精度为小数点后 8 位。如果其价格为 0.00000011 —— 那么往上一个价格台阶将是 0.00000012，这比之前的价格值高了约 9%。您可以通过使用 `low_price_ratio` 设置为 0.09 (9%) 或 `min_price` 为 0.00000011 的 PriceFilter 过滤掉此对。

!!! Warning "低价对"
    具有高 "1 pip movement" 的低价对是危险的，因为它们通常流动性不足，且可能无法放置所需的止损。这通常会导致巨大的损失，因为价格需要舍入到下一个可交易价格 —— 因此原本止损率为 -5% 时，可能由于价格舍入最终止损率为 -9%。

#### ShuffleFilter

对列表中的交易对进行洗牌（随机化）。当您希望所有对都以相同的优先级对待时，它可以用来防止机器人更频繁地交易某些对。

默认情况下，ShuffleFilter 在每根 K 线内对交易对洗牌一次。
要在每次迭代时都进行洗牌，请将 `"shuffle_frequency"` 设置为 `"iteration"`，而非默认的 `"candle"`。

``` json
    {
        "method": "ShuffleFilter", 
        "shuffle_frequency": "candle",
        "seed": 42
    }

```

!!! Tip
    您可以为该处理器设置 `seed`（种子）值以获得可重复的结果，这在重复的回测会话中很有用。如果未设置 `seed`，则交易对将以不可重复的随机顺序洗牌。如果设置了 `seed`，ShuffleFilter 将自动检测运行模式，并仅对回测模式应用 `seed`。

#### SpreadFilter

移除卖价和买价之差高于指定比率 `max_spread_ratio`（默认为 `0.005`）的对。

示例：

如果 `DOGE/BTC` 的最高买价为 0.00000026，最低卖价为 0.00000027，则比率计算为：`1 - 买价/卖价 ~= 0.037`。由于这个值 `> 0.005`，因此该对将被过滤掉。

#### RangeStabilityFilter

移除在 `lookback_days` 天内的最低价和最高价之间的差值低于 `min_rate_of_change` 或高于 `max_rate_of_change` 的对。由于这是一个需要额外数据的过滤器，结果会缓存 `refresh_period`。

在下面的示例中：
如果过去 10 天内的交易范围 <1% 或 >99%，则将该对从白名单中删除。

```json
"pairlists": [
    {
        "method": "RangeStabilityFilter",
        "lookback_days": 10,
        "min_rate_of_change": 0.01,
        "max_rate_of_change": 0.99,
        "refresh_period": 86400
    }
]
```

添加 `"sort_direction": "asc"` 或 `"sort_direction": "desc"` 可以启用此对名单的排序功能。

!!! Tip
    此过滤器可用于自动移除波动范围极低的稳定币对，因为这类对极难获得盈利。
    此外，它还可以用于自动移除在给定时间内具有极端高/低方差的对。

#### VolatilityFilter

波动率是指价格随时间变化的历史变异程度，它通过每日对数收益的标准偏差来衡量。假设收益服从正态分布，尽管实际分布可能有所不同。在正态分布中，68% 的观察值落在一个标准偏差内，95% 的观察值落在两个标准偏差内。假设波动率为 0.05，则意味着预期在 30 天中有 20 天收益预计小于 5%（一个标准偏差）。波动率是预期收益离差的正比率，可以大于 1.00。请参阅维基百科关于 [`volatility`](https://en.wikipedia.org/wiki/Volatility_(finance))（波动率）的定义。

如果 `lookback_days` 天内的平均波动率低于 `min_volatility` 或高于 `max_volatility`，此过滤器将移除对应的对。由于这是一个需要额外数据的过滤器，结果会缓存 `refresh_period`。

此过滤器可用于将交易对限制在一定波动范围内，或避免过于波动的对。

在下面的示例中：
如果过去 10 天内的波动率不在 0.05-0.50 范围内，则将该对从白名单中删除。该过滤器每 24h 应用一次。

```json
"pairlists": [
    {
        "method": "VolatilityFilter",
        "lookback_days": 10,
        "min_volatility": 0.05,
        "max_volatility": 0.50,
        "refresh_period": 86400
    }
]
```

添加 `"sort_direction": "asc"` 或 `"sort_direction": "desc"` 可以启用此对名单的排序模式。

### 交易对列表处理器的完整示例

下例将 `BNB/BTC` 列入黑名单，使用包含 `20` 个资产的 `VolumePairList` 处理器，按 `quoteVolume` 对交易对进行排序，然后使用 [`DelistFilter`](#delistfilter) 过滤未来下架的币种，并使用 [`AgeFilter`](#agefilter) 移除上市时间不足 10 天的对。之后应用 [`PrecisionFilter`](#precisionfilter) 和 [`PriceFilter`](#pricefilter)，过滤掉 1 个价格单位 > 1% 的所有资产。接着应用 [`SpreadFilter`](#spreadfilter) 和 [`VolatilityFilter`](#volatilityfilter)，最后将随机种子设置为某些预定义值并洗乱交易对顺序。

```json
"exchange": {
    "pair_whitelist": [],
    "pair_blacklist": ["BNB/BTC"]
},
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 20,
        "sort_key": "quoteVolume"
    },
    {
        "method": "DelistFilter",
        "max_days_from_now": 0,
    },
    {"method": "AgeFilter", "min_days_listed": 10},
    {"method": "PrecisionFilter"},
    {"method": "PriceFilter", "low_price_ratio": 0.01},
    {"method": "SpreadFilter", "max_spread_ratio": 0.005},
    {
        "method": "RangeStabilityFilter",
        "lookback_days": 10,
        "min_rate_of_change": 0.01,
        "refresh_period": 86400
    },
    {
        "method": "VolatilityFilter",
        "lookback_days": 10,
        "min_volatility": 0.05,
        "max_volatility": 0.50,
        "refresh_period": 86400
    },
    {"method": "ShuffleFilter", "seed": 42}
],
```
---
原始文件来源: [docs/includes/pairlists.md](docs/includes/pairlists.md)
