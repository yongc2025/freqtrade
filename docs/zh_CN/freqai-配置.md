# FreqAI 配置 (Configuration)

FreqAI 通过典型的 [Freqtrade 配置文件](配置文件说明.md) 和标准的 [Freqtrade 策略](策略自定义.md) 进行配置。可在 `config_examples/config_freqai.example.json` 和 `freqtrade/templates/FreqaiExampleStrategy.py` 中分别找到 FreqAI 配置和策略文件的示例。

## 设置配置文件

虽然有很多额外的参数可供选择，正如在 [参数表](freqai-parameter-table.md#参数表) 中突出显示的，但 FreqAI 配置必须至少包含以下参数（参数值仅为示例）：

```json
    "freqai": {
        "enabled": true,
        "purge_old_models": 2,
        "train_period_days": 30,
        "backtest_period_days": 7,
        "identifier" : "unique-id",
        "feature_parameters" : {
            "include_timeframes": ["5m","15m","4h"],
            "include_corr_pairlist": [
                "ETH/USD",
                "LINK/USD",
                "BNB/USD"
            ],
            "label_period_candles": 24,
            "include_shifted_candles": 2,
            "indicator_periods_candles": [10, 20]
        },
        "data_split_parameters" : {
            "test_size": 0.25
        }
    }
```

完整的示例配置可在 `config_examples/config_freqai.example.json` 中找到。

!!! Note "注意"
    `identifier` (标识符) 经常被新手忽视，然而，这个值在您的配置中起着重要作用。该值是您为描述其中一次运行而选择的唯一 ID。保持不变可以使您维持崩溃弹性以及更快的测试。一旦您想尝试新的运行（新功能、新模型等），您应该更改此值（或删除 `user_data/models/unique-id` 文件夹）。更多细节可在 [参数表](freqai-parameter-table.md#特征参数) 中找到。

## 构建 FreqAI 策略

FreqAI 策略要求在标准的 [Freqtrade 策略](策略自定义.md) 中包含以下代码行：

```python
    # 用户应定义最大启动 K 线计数（传递给任何单个指标的最大 K 线数）
    startup_candle_count: int = 20

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # 模型将返回用户在 `set_freqai_targets()` 中创建的所有标签（以及附带目标）、
        # 是否接受该预测的指示，以及用户在 `set_freqai_targets()` 中为每个训练周期创建的
        # 各个标签的目标均值/标准差值。

        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def feature_engineering_expand_all(self, dataframe: DataFrame, period, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此函数将根据配置中定义的 `indicator_periods_candles`、`include_timeframes`、
        `include_shifted_candles` 和 `include_corr_pairs` 自动展开定义的特征。
        换句话说，此函数中定义的一个特征将自动展开为总共
        `indicator_periods_candles` * `include_timeframes` * `include_shifted_candles` *
        `include_corr_pairs` 数量的特征并添加到模型中。

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        :param df: 接收特征的策略 dataframe
        :param period: 指标的周期 —— 使用示例：
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        """

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此函数将根据配置中定义的 `include_timeframes`、`include_shifted_candles`
        和 `include_corr_pairs` 自动展开定义的特征。
        换句话说，此函数中定义的一个特征将自动展开为总共
        `include_timeframes` * `include_shifted_candles` * `include_corr_pairs`
        数量的特征并添加到模型中。

        此处定义的特征 *不会* 自动按用户定义的 `indicator_periods_candles` 复制。

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        :param df: 接收特征的策略 dataframe
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-ema-200"] = ta.EMA(dataframe, timeperiod=200)
        """
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此可选函数将在基础时间范围的 dataframe 上调用一次。
        这是最后一个调用的函数，这意味着进入该函数的 dataframe 将包含由所有其他
        freqai_feature_engineering_* 函数创建的所有特征和列。

        此函数适合进行自定义奇特特征提取（例如 tsfresh）。
        此函数适合放置任何不应自动展开的特征（例如星期几）。

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        :param df: 接收特征的策略 dataframe
        使用示例：dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        """
        dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        dataframe["%-hour_of_day"] = (dataframe["date"].dt.hour + 1) / 25
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        设置模型目标的必选函数。
        所有目标必须前缀 `&` 才能被 FreqAI 内部识别。

        :param df: 接收目标的策略 dataframe
        使用示例：dataframe["&-target"] = dataframe["close"].shift(-1) / dataframe["close"]
        """
        dataframe["&-s_close"] = (
            dataframe["close"]
            .shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
            .rolling(self.freqai_info["feature_parameters"]["label_period_candles"])
            .mean()
            / dataframe["close"]
            - 1
            )
        return dataframe
```

请注意，`feature_engineering_*()` 是添加 [特征 (features)](freqai-feature-engineering.md#特征工程) 的地方。而 `set_freqai_targets()` 则添加标签/目标。在 `templates/FreqaiExampleStrategy.py` 中提供了一个完整的策略示例。

!!! Note "注意"
    `self.freqai.start()` 函数不能在 `populate_indicators()` 之外调用。

!!! Note "注意"
    特征 **必须** 在 `feature_engineering_*()` 中定义。在 `populate_indicators()` 中定义 FreqAI 特征会导致算法在实盘/干盘模式下失败。为了添加不与特定交易对或时间范围关联的通用特征，您应该使用 `feature_engineering_standard()`（如 `freqtrade/templates/FreqaiExampleStrategy.py` 示例所示）。

## 重要 Dataframe 键名模式

以下是您可以在典型策略 dataframe (`df[]`) 中包含/使用的常见值：

|  Dataframe 键名 | 描述 |
|------------|-------------|
| `df['&*']` | 在 `set_freqai_targets()` 中任何前缀为 `&` 的 dataframe 列都被 FreqAI 视为训练目标（标签）（通常遵循 `&-s*` 命名规范）。例如，要预测 40 根 K 线后的收盘价，您可以设置 `df['&-s_close'] = df['close'].shift(-self.freqai_info["feature_parameters"]["label_period_candles"])` 并在配置中设置 `"label_period_candles": 40`。FreqAI 会进行预测并将结果以相同的键名（`df['&-s_close']`）返回，供 `populate_entry/exit_trend()` 使用。<br> **数据类型**：取决于模型输出。
| `df['&*_std/mean']` | 定义标签在训练期间（或使用 `fit_live_predictions_candles` 进行实时跟踪）的标准差和均值。常用于了解预测值的罕见程度（使用 `templates/FreqaiExampleStrategy.py` 所示的 z-score，以及 [在此解释](#创建动态目标阈值) 的方法来评估特定预测在训练期间或以往通过 `fit_live_predictions_candles` 记录的历史预测中观察到的频率）。<br> **数据类型**：浮点数。
| `df['do_predict']` | 离群数据点的指示。返回值为 -2 到 2 之间的整数，让您知道预测是否值得信赖。`do_predict==1` 表示预测是可信的。如果输入数据点的差异指数（DI，详见 [此处](freqai-feature-engineering.md#使用差异指数-di-识别离群值)）高于配置中定义的阈值，FreqAI 将从 `do_predict` 中减去 1，结果为 `do_predict==0`。如果启用了 `use_SVM_to_remove_outliers`，支持向量机（SVM，详见 [此处](freqai-feature-engineering.md#使用支持向量机-svm-识别离群值)）也可能在训练和预测数据中检测到离群值。在这种情况下，SVM 也会从 `do_predict` 中减去 1。如果输入数据点被 SVM 认为是离群值，但 DI 没有认为，反之亦然，结果将是 `do_predict==0`。如果 DI 和 SVM 都认为输入数据点是离群值，结果将是 `do_predict==-1`。与 SVM 类似，如果启用了 `use_DBSCAN_to_remove_outliers`，DBSCAN（详见 [此处](freqai-feature-engineering.md#使用-dbscan-识别离群值)）也可能检测到离群值并从 `do_predict` 中减去 1。因此，如果 SVM 和 DBSCAN 都启用，并识别一个高于 DI 阈值的数据点为离群值，结果将是 `do_predict==-2`。一个特殊情况是 `do_predict == 2`，这意味着由于超过了 `expired_hours`，模型已过期。<br> **数据类型**：-2 到 2 之间的整数。
| `df['DI_values']` | 差异指数 (DI) 值是 FreqAI 对预测信心的代理指标。较低的 DI 意味着预测值接近训练数据，即预测信心更高。关于 DI 的详情请见 [此处](freqai-feature-engineering.md#使用差异指数-di-识别离群值)。<br> **数据类型**：浮点数。
| `df['%*']` | 在 `feature_engineering_*()` 中任何前缀为 `%` 的 dataframe 列都被视为训练特征。例如，通过设置 `df['%-rsi']` 可以将 RSI 包含在训练特征集中（类似于 `templates/FreqaiExampleStrategy.py`）。更多关于如何操作的详情请见 [此处](freqai-feature-engineering.md)。<br> **注意**：由于前缀为 `%` 的特征数量会迅速倍增（利用 `include_shifted_candles` 和 `include_timeframes` 等乘法功能，很容易设计出上万个特征，详见 [参数表](freqai-parameter-table.md)），这些特征会从 FreqAI 返回给策略的 dataframe 中移除。如需保留某种特定类型的特征用于绘图，应为其添加前缀 `%%`（详见下文）。<br> **数据类型**：取决于用户创建的特征。
| `df['%%*']` | 在 `feature_engineering_*()` 中任何前缀为 `%%` 的 dataframe 列都被视为训练特征，与上述 `%` 前缀相同。但在此情况下，特征会返回给策略，以便在干跑/实盘/回测中进行 FreqUI/图表绘制和监控。<br> **数据类型**：取决于用户创建的特征。请注意，在 `feature_engineering_expand()` 中创建的特征会有自动的 FreqAI 命名规则，具体取决于您配置的展开（即 `include_timeframes`, `include_corr_pairlist`, `indicators_periods_candles`, `include_shifted_candles`）。例如，如果您想在绘图配置中绘制来自 `feature_engineering_expand_all()` 的 `%%-rsi`，最终的命名规则应为：`%%-rsi-period_10_ETH/USDT:USDT_1h`（针对 `period=10`、`timeframe=1h` 以及 `pair=ETH/USDT:USDT` 的 `rsi` 特征；如果您使用的是期货交易对，则会加上 `:USDT` 后缀）。只需在 `populate_indicators()` 中的 `self.freqai.start()` 之后添加 `print(dataframe.columns)`，即可查看返回给策略的所有可用特征列表。

## 设置 `startup_candle_count`

FreqAI 策略中的 `startup_candle_count` 需要按照标准 Freqtrade 策略进行设置（详见 [此处](策略自定义.md#策略启动期)）。Freqtrade 使用此值确保调用 `dataprovider` 时提供足够的数据量，以避免在第一次训练开始时出现 NaN。您可以很容易地通过识别传递给指标创建函数（如 TA-Lib 函数）的最长周期（以 K 线为单位）来设置此值。在呈现的示例中，`startup_candle_count` 是 20，因为这是 `indicators_periods_candles` 中的最大值。

!!! Note "注意"
    有时候，TA-Lib 函数实际上需要的数据比传递的 `period` 更多，否则特征数据集会填充 NaN。据经验显示，将 `startup_candle_count` 乘以 2 总是能得到一个完全无 NaN 的训练数据集。因此，通常将预期的 `startup_candle_count` 乘以 2 是最稳妥的。通过这一日志消息可以确认数据是否干净：

    ```
    2022-08-31 15:14:04 - freqtrade.freqai.data_kitchen - INFO - dropped 0 training points due to NaNs in populated dataset 4319.
    ```

## 创建动态目标阈值

决定何时入场或出场交易可以以动态的方式进行，以反映当前的市场状况。FreqAI 允许您从模型的训练中返回额外信息（更多详情见 [此处](freqai-feature-engineering.md#从训练中返回额外信息)）。例如，`&*_std/mean` 返回值描述了 *最近一次训练期间* 目标/标签的统计分布。将给定的预测值与这些值进行比较，可以让您了解预测的罕见程度。在 `templates/FreqaiExampleStrategy.py` 中，`target_roi` 和 `sell_roi` 被定义为距离均值 1.25 个 z-score，这使得更接近均值的预测会被过滤掉。

```python
dataframe["target_roi"] = dataframe["&-s_close_mean"] + dataframe["&-s_close_std"] * 1.25
dataframe["sell_roi"] = dataframe["&-s_close_mean"] - dataframe["&-s_close_std"] * 1.25
```

如果想通过考虑 *历史预测* 总体来创建动态目标，而不是讨论中提到的来自训练的信息，您可以将配置中的 `fit_live_predictions_candles` 设置为您希望用于生成目标统计数据的历史预测 K 线数量。

```json
    "freqai": {
        "fit_live_predictions_candles": 300,
    }
```

如果设置了此值，FreqAI 初期将使用训练数据中的预测值，随后随着实际预测数据的生成而开始引入它们。如果您停止并使用相同的 `identifier` 重启一个模型，FreqAI 将保存这些历史数据以便重新加载。

## 使用不同的预测模型

FreqAI 拥有多个开箱即用的预测模型库示例，通过旗标 `--freqaimodel` 即可直接使用。这些库包括 `LightGBM` 和 `XGBoost` 的回归、分类及多目标模型，可在 `freqai/prediction_models/` 中找到。

回归模型和分类模型的不同之处在于它们预测的目标 —— 回归模型预测的是连续值的目标，例如明天的 BTC 价格；而分类器预测的是离散值的目标，例如明天的 BTC 价格是涨还是不涨。这意味着您必须根据使用的模型类型以不同的方式指定目标（详见 [下文](#设置模型目标)）。

上述所有模型库都实现了梯度提升决策树 (GBDT) 算法。它们都基于集成学习 (ensemble learning) 的原理，即将多个简单学习器的预测结果结合起来，得到更稳定且更通用的最终预测。在这里，简单学习器指的是决策树。梯度提升指的是学习方法，即按顺序构建每个简单学习器 —— 后续的学习器用于修正前一个学习器的错误。如果您想进一步了解不同的模型库，可以在其各自文档中找到信息：

* LightGBM: <https://lightgbm.readthedocs.io/en/v3.3.2/#>
* XGBoost: <https://xgboost.readthedocs.io/en/stable/#>
* CatBoost: <https://catboost.ai/en/docs/> (自 2025.12 起不再处于活跃支持状态)

网上也有大量描述和比较这些算法的文章。一些相对浅显的例子包括：[CatBoost vs. LightGBM vs. XGBoost — 哪个是最好的算法？](https://towardsdatascience.com/catboost-vs-lightgbm-vs-xgboost-c80f40662924#:~:text=In%20CatBoost%2C%20symmetric%20trees%2C%20or,the%20same%20depth%20can%20differ.) 以及 [XGBoost, LightGBM or CatBoost — 我该用哪种 boosting 算法？](https://medium.com/riskified-technology/xgboost-lightgbm-or-catboost-which-boosting-algorithm-should-i-use-e7fda7bb36bc)。请记住，每个模型的性能高度依赖于实际应用场景，因此任何公布的指标对您的特定模型用途可能并不准确。

除了 FreqAI 已经提供的模型外，还可以使用 `IFreqaiModel` 类来定制和创建您自己的预测模型。我们鼓励您继承并重写 `fit()`、`train()` 和 `predict()` 以定制训练程序的各个方面。您可以将自定义 FreqAI 模型放在 `user_data/freqaimodels` 下 —— freqtrade 将根据提供的 `--freqaimodel` 名称并匹配类名来加载它们。请务必使用唯一的名称以避免覆盖内置模型。

### 设置模型目标

#### 回归模型 (Regressors)

如果您使用的是回归模型，需要指定一个具有连续值的目标。FreqAI 包含多种回归模型，如 `LightGBMRegressor`（通过旗标 `--freqaimodel LightGBMRegressor` 调用）。设置回归目标预测 100 根 K 线之后的价格示例：

```python
df['&s-close_price'] = df['close'].shift(-100)
```

如果您想预测多个目标，需要使用上述相同的语法定义多个标签。

#### 分类器 (Classifiers)

如果您使用的是分类器，需要指定一个具有离散值的目标。FreqAI 包含多种分类器，如 `LightGBMClassifier`（通过旗标 `--freqaimodel LightGBMClassifier` 调用）。如果您选择使用分类器，类别需要使用字符串设置。例如，预测 100 根 K 线之后的价格是涨还是跌：

```python
df['&s-up_or_down'] = np.where( df["close"].shift(-100) > df["close"], 'up', 'down')
```

如果您想预测多个目标，必须在同一个标签列中指定所有标签。例如，您可以添加 `same` 标签来定义价格不变的情况：

```python
df['&s-up_or_down'] = np.where( df["close"].shift(-100) > df["close"], 'up', 'down')
df['&s-up_or_down'] = np.where( df["close"].shift(-100) == df["close"], 'same', df['&s-up_or_down'])
```

## PyTorch 模块

### 快速上手

快速运行 PyTorch 模型（回归任务）的最简单方法是使用以下命令：

```bash
freqtrade trade --config config_examples/config_freqai.example.json --strategy FreqaiExampleStrategy --freqaimodel PyTorchMLPRegressor --strategy-path freqtrade/templates 
```

!!! Note "安装/Docker"
    PyTorch 模块需要大型软件包（如 `torch`），应在 `./setup.sh -i` 期间针对“您是否还需要 freqai-rl 或 PyTorch 的依赖项（~700mb 额外空间）[y/N]？”问题回答 "y" 来显式请求安装。
    偏好 Docker 的用户应确保使用以 `_freqaitorch` 结尾的 Docker 映像。
    我们在 `docker/docker-compose-freqai.yml` 中提供了一个明确的 Docker Compose 文件 —— 可以通过 `docker compose -f docker/docker-compose-freqai.yml run ...` 使用，也可以复制替换原本的 Docker 文件。该 Docker Compose 文件同样包含一个（禁用的）部分用于在容器内启用 GPU 资源，这显然假设系统具备 GPU。
    PyTorch 在 2.3 版本中停止了对 macOS x64（基于 Intel 的 Apple 设备）的支持，随后 freqtrade 也停止了在该平台对 PyTorch 的支持。

### 结构

#### 模型 (Model)

您可以通过在自定义 [`IFreqaiModel` 文件](#使用不同的预测模型) 中定义 `nn.Module` 类，然后在 `def train()` 函数中使用该类，来构建您自己的神经网络架构。以下是使用 PyTorch 实现逻辑回归模型（应配合 nn.BCELoss 使用）进行分类任务的示例：

```python

class LogisticRegression(nn.Module):
    def __init__(self, input_size: int):
        super().__init__()
        # 定义您的网络层
        self.linear = nn.Linear(input_size, 1)
        self.activation = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 定义前向传播
        out = self.linear(x)
        out = self.activation(out)
        return out

class MyCoolPyTorchClassifier(BasePyTorchClassifier):
    """
    这是一个自定义 IFreqaiModel，展示了用户如何为其训练设置自定义神经网络架构。
    """

    @property
    def data_convertor(self) -> PyTorchDataConvertor:
        return DefaultPyTorchDataConvertor(target_tensor_type=torch.float)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        config = self.freqai_info.get("model_training_parameters", {})
        self.learning_rate: float = config.get("learning_rate",  3e-4)
        self.model_kwargs: dict[str, Any] = config.get("model_kwargs",  {})
        self.trainer_kwargs: dict[str, Any] = config.get("trainer_kwargs",  {})

    def fit(self, data_dictionary: dict, dk: FreqaiDataKitchen, **kwargs) -> Any:
        """
        在此处设置训练和测试数据以拟合所需的模型
        :param data_dictionary: 存储所有数据的字典，包括 train, test, labels, weights
        :param dk: 当前币种/模型的 datakitchen 对象
        """

        class_names = self.get_class_names()
        self.convert_label_column_to_int(data_dictionary, dk, class_names)
        n_features = data_dictionary["train_features"].shape[-1]
        model = LogisticRegression(
            input_dim=n_features
        )
        model.to(self.device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=self.learning_rate)
        criterion = torch.nn.CrossEntropyLoss()
        init_model = self.get_init_model(dk.pair)
        trainer = PyTorchModelTrainer(
            model=model,
            optimizer=optimizer,
            criterion=criterion,
            model_meta_data={"class_names": class_names},
            device=self.device,
            init_model=init_model,
            data_convertor=self.data_convertor,
            **self.trainer_kwargs,
        )
        trainer.fit(data_dictionary, self.splits)
        return trainer

```

#### 训练器 (Trainer)

`PyTorchModelTrainer` 执行惯用的 PyTorch 训练循环：定义模型、损失函数和优化器，然后将它们移动到适当的设备（GPU 或 CPU）。在循环内，通过 dataloader 迭代 batch，将数据移至设备，计算预测和损失，进行反向传播，并使用优化器更新模型参数。

此外，训练器还负责以下工作：
 - 保存和加载模型
 - 将数据从 `pandas.DataFrame` 转换为 `torch.Tensor`。

#### 与 Freqai 模块集成

与所有 freqai 模型一样，PyTorch 模型继承自 `IFreqaiModel`。`IFreqaiModel` 声明了三个抽象方法：`train`、`fit` 和 `predict`。我们在三个等级的继承层次中实现了这些方法，从上到下依次为：

1. `BasePyTorchModel` - 实现 `train` 方法。所有的 `BasePyTorch*` 都继承它。负责通用的数据准备（如数据归一化）并调用 `fit` 方法。设置供子类使用的 `device` 属性。设置父类使用的 `model_type` 属性。
2. `BasePyTorch*` - 实现 `predict` 方法。此处 `*` 代表一类算法，如分类器或回归器。负责数据预处理、预测及必要的后处理。
3. `PyTorch*Classifier` / `PyTorch*Regressor` - 实现 `fit` 方法。负责主要的训练流程，在这里初始化训练器和模型对象。

![image](../assets/freqai_pytorch-diagram.png)

#### 完整示例

使用 MLP (多层感知器) 模型、MSELoss 判据和 AdamW 优化器构建一个 PyTorch 回归器。

```python
class PyTorchMLPRegressor(BasePyTorchRegressor):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        config = self.freqai_info.get("model_training_parameters", {})
        self.learning_rate: float = config.get("learning_rate",  3e-4)
        self.model_kwargs: dict[str, Any] = config.get("model_kwargs",  {})
        self.trainer_kwargs: dict[str, Any] = config.get("trainer_kwargs",  {})

    def fit(self, data_dictionary: dict, dk: FreqaiDataKitchen, **kwargs) -> Any:
        n_features = data_dictionary["train_features"].shape[-1]
        model = PyTorchMLPModel(
            input_dim=n_features,
            output_dim=1,
            **self.model_kwargs
        )
        model.to(self.device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=self.learning_rate)
        criterion = torch.nn.MSELoss()
        init_model = self.get_init_model(dk.pair)
        trainer = PyTorchModelTrainer(
            model=model,
            optimizer=optimizer,
            criterion=criterion,
            device=self.device,
            init_model=init_model,
            target_tensor_type=torch.float,
            **self.trainer_kwargs,
        )
        trainer.fit(data_dictionary)
        return trainer
```

在这里我们创建了一个 `PyTorchMLPRegressor` 类并实现了 `fit` 方法。`fit` 方法指定了训练的构建块：模型、优化器、判据和训练器。我们同时继承了 `BasePyTorchRegressor` 和 `BasePyTorchModel`，前者实现了适合回归任务的 `predict` 方法，后者实现了训练方法。

??? Note "设置分类器的类名"
    当使用分类器时，用户必须通过覆盖 `IFreqaiModel.class_names` 属性来声明类名（或目标）。这可以通过在 FreqAI 策略的 `set_freqai_targets` 方法中设置 `self.freqai.class_names` 来实现。

    例如，如果您使用二元分类器来预测价格变动的涨跌，可以按如下方式设置类名：
    ```python
    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-100) >
                                                  dataframe["close"], 'up', 'down')
    
        return dataframe
    ```
    查看完整示例可以参考 [分类器测试策略类](https://github.com/freqtrade/freqtrade/blob/develop/tests/strategy/strats/freqai_test_classifier.py)。


#### 使用 `torch.compile()` 提升性能

Torch 提供了一个 `torch.compile()` 方法，可用于提升特定 GPU 硬件的性能。更多详情可在 [此处](https://pytorch.org/tutorials/intermediate/torch_compile_tutorial.html) 找到。简而言之，只需在 `torch.compile()` 中包装您的 `model` 即可：

```python
        model = PyTorchMLPModel(
            input_dim=n_features,
            output_dim=1,
            **self.model_kwargs
        )
        model.to(self.device)
        model = torch.compile(model)
```

然后正常使用模型。请记住，这样做会移除动态执行功能，这意味着报错和调用栈跟踪将不再具有参考价值。

---

原始文件来源: [docs/freqai-configuration.md](docs/freqai-configuration.md)
