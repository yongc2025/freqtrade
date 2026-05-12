# 特征工程 (Feature Engineering)

## 定义特征

底层的特征工程在用户策略中通过一组名为 `feature_engineering_*` 的函数来执行。这些函数设置了“基础特征 (base features)”，例如 `RSI`、`MFI`、`EMA`、`SMA`、当日时间、成交量等。基础特征可以是自定义指标，也可以是从您能找到的任何技术分析库中导入。FreqAI 配备了一组函数，用以简化快速的大规模特征工程：

| 函数 | 描述 |
|---------------|-------------|
| `feature_engineering_expand_all()` | 此可选函数将根据配置中定义的 `indicator_periods_candles`、`include_timeframes`、`include_shifted_candles` 和 `include_corr_pairs` 自动展开定义的特征。
| `feature_engineering_expand_basic()` | 此可选函数将根据配置中定义的 `include_timeframes`、`include_shifted_candles` 和 `include_corr_pairs` 自动展开定义的特征。注意：此函数 *不会* 跨 `indicator_periods_candles` 展开。
| `feature_engineering_standard()` | 此可选函数将针对基础时间范围的 dataframe 调用一次。这是最后一个被调用的函数，这意味着进入该函数的 dataframe 将包含由其他 `feature_engineering_expand` 函数创建的基础资产的所有特征和列。此函数适合进行自定义的特殊特征提取（例如 tsfresh）。此函数也适合放置任何不应自动展开的特征（例如星期几）。
| `set_freqai_targets()` | 必选函数，用于为模型设置目标（标签）。所有目标必须前缀 `&` 才能被 FreqAI 内部识别。

同时，高层特征工程在 FreqAI 配置文件的 `"feature_parameters":{}` 中处理。在配置文件中，可以基于 `base_features` 决定大规模的特征展开，例如“包含关联交易对”、“包含包含性时间范围”甚至“包含最近的 K 线”。

建议从提供的示例策略（位于 `templates/FreqaiExampleStrategy.py`）中的 `feature_engineering_*` 函数模板开始，以确保特征定义遵循正确的约定。以下是如何在策略中设置指标和标签的示例：

```python
    def feature_engineering_expand_all(self, dataframe: DataFrame, period, metadata, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此函数将根据配置定义的 `indicator_periods_candles`、`include_timeframes`、
        `include_shifted_candles` 和 `include_corr_pairs` 自动展开定义的特征。
        换句话说，此函数中定义的一个特征将自动展开为总共
        `indicator_periods_candles` * `include_timeframes` * `include_shifted_candles` *
        `include_corr_pairs` 数量的特征并添加到模型中。

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        通过以下方式访问元数据（如当前交易对/时间范围/周期）：
        `metadata["pair"]` `metadata["tf"]` `metadata["period"]`

        :param df: 接收特征的策略 dataframe
        :param period: 指标的周期 —— 使用示例：
        :param metadata: 当前交易对的元数据
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        """

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"]
            - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe["bb_lowerband-period"]
        )

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此函数将根据配置定义的 `include_timeframes`、`include_shifted_candles` 和
        `include_corr_pairs` 自动展开定义的特征。
        换句话说，此函数中定义的一个特征将自动展开为总共
        `include_timeframes` * `include_shifted_candles` * `include_corr_pairs`
        数量的特征并添加到模型中。

        此处定义的特征 *不会* 在用户定义的 `indicator_periods_candles` 上自动重复。

        通过以下方式访问元数据（如当前交易对/时间范围）：
        `metadata["pair"]` `metadata["tf"]`

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        :param df: 接收特征的策略 dataframe
        :param metadata: 当前交易对的元数据
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-ema-200"] = ta.EMA(dataframe, timeperiod=200)
        """
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        此可选函数将针对基础时间范围的 dataframe 调用一次。
        这是最后一个调用的函数，这意味着进入该函数的 dataframe 将包含由所有其他
        freqai_feature_engineering_* 函数创建的所有特征和列。

        此函数适合进行自定义的特殊特征提取（例如 tsfresh）。
        此函数适合放置任何不应自动展开的特征（例如星期几）。

        通过以下方式访问元数据（如当前交易对）：
        `metadata["pair"]`

        所有特征必须前缀 `%` 才能被 FreqAI 内部识别。

        :param df: 接收特征的策略 dataframe
        :param metadata: 当前交易对的元数据
        使用示例：dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        """
        dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        dataframe["%-hour_of_day"] = (dataframe["date"].dt.hour + 1) / 25
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        必选函数，用于为模型设置目标。
        所有目标必须前缀 `&` 才能被 FreqAI 内部识别。

        通过以下方式访问元数据（如当前交易对）：
        `metadata["pair"]`

        :param df: 接收目标的策略 dataframe
        :param metadata: 当前交易对的元数据
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

在给出的示例中，用户不希望将 `bb_lowerband` 作为特征传递给模型，因此没有为其加前缀 `%`。但是，用户希望将 `bb_width` 传递给模型用于训练/预测，因此为其加了前缀 `%`。

定义好基础特征后，下一步是使用配置文件中强大的 `feature_parameters` 进行展开：

```json
    "freqai": {
        //...
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
        //...
    }
```

上述配置中的 `include_timeframes` 是策略中每次调用 `feature_engineering_expand_*()` 时使用的时间范围 (`tf`)。在此示例中，用户要求将 `5m`、`15m` 和 `4h` 时间范围内的 `rsi`、`mfi`、`roc` 和 `bb_width` 包含在特征集中。

您也可以通过 `include_corr_pairlist` 要求将定义的特征也包含在相关性交易对中。这意味着特征集将包含针对配置中定义的每个相关性交易对（示例中为 `ETH/USD`, `LINK/USD`, 和 `BNB/USD`）在所有 `include_timeframes` 上通过 `feature_engineering_expand_*()` 生成的所有特征。

`include_shifted_candles` 表示要包含在特征集中的前几根 K 线数量。例如，`include_shifted_candles: 2` 告诉 FreqAI 为特征集中的每个特征包含过去 2 根 K 线的数据。

总计，该示例策略用户创建的特征数量为：`include_timeframes` 长度 * `feature_engineering_expand_*()` 特征数 * `include_corr_pairlist` 长度 * `include_shifted_candles` 数量 * `indicator_periods_candles` 长度
$= 3 * 3 * 3 * 2 * 2 = 108$。
 
!!! note "了解更多关于创意特征工程的信息"
    查看我们的 [Medium 文章](https://emergentmethods.medium.com/freqai-from-price-to-prediction-6fadac18b665)，旨在帮助用户学习如何有创意地设计特征。

### 通过 `metadata` 获得对 `feature_engineering_*` 函数的更精细控制

所有的 `feature_engineering_*` 和 `set_freqai_targets()` 函数都会被传递一个 `metadata` 字典，其中包含 FreqAI 自动化特征构建时关于 `pair` (交易对)、`tf` (时间范围) 和 `period` (周期) 的信息。因此，用户可以在这些函数中使用 `metadata` 作为标准，针对特定时间范围、周期、交易对等屏蔽或保留特征。

```python
def feature_engineering_expand_all(self, dataframe: DataFrame, period, metadata, **kwargs) -> DataFrame:
    if metadata["tf"] == "1h":
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
```

这将阻止 `ta.ROC()` 被添加到除 `"1h"` 以外的任何时间范围。

### 从训练中返回额外信息

自定义预测模型类中，通过将其赋值给 `dk.data['extra_returns_per_train']['my_new_value'] = XYZ`，可以在每次模型训练结束时将重要指标返回给策略。

FreqAI 获取该字典中赋值的 `my_new_value`，并将其展开以匹配返回给策略的 dataframe。随后您可以在策略中通过 `dataframe['my_new_value']` 使用返回的指标。在 FreqAI 中，返回值的一个应用案例是 `&*_mean` 和 `&*_std` 值，它们被用于 [创建动态目标阈值](freqai-配置.md#创建动态目标阈值)。

下文展示了另一个示例，用户希望使用来自交易数据库的实时指标：

```json
    "freqai": {
        "extra_returns_per_train": {"total_profit": 4}
    }
```

您需要在配置中设置标准字典，以便 FreqAI 能够返回正确的 dataframe 形状。这些值很可能会被预测模型覆盖，但在模型尚未设置它们或需要默认初始值的情况下，将返回这些预设值。

### 针对时间重要性设置特征权重

FreqAI 允许您通过指数函数设置 `weight_factor`（权重因子），使近期数据比历史数据具有更高的权重：

$$ W_i = \exp(\frac{-i}{\alpha*n}) $$

其中 $W_i$ 是总共 $n$ 个数据点中数据点 $i$ 的权重。下图显示了不同权重因子对特征集中数据点的影响。

![weight-factor](../assets/freqai_weight-factor.jpg)

## 构建数据管道

默认情况下，FreqAI 根据用户配置设置构建动态管道。默认设置非常稳健，旨在适用于多种方法。这两个默认步骤是 `MinMaxScaler(-1,1)` 和移除任何方差为 0 的列的 `VarianceThreshold`。用户可以通过更多配置参数激活其他步骤。例如，如果用户在 `freqai` 配置中添加 `use_SVM_to_remove_outliers: true`，FreqAI 将自动在管道中添加 [`SVMOutlierExtractor`](#使用支持向量机-svm-识别离群值)。同样，用户可以通过在 `freqai` 配置中添加 `principal_component_analysis: true` 来激活 PCA。使用 `DI_threshold: 1` 激活 [差异指数 (DissimilarityIndex)](#使用差异指数-di-识别离群值)。此外，还可以使用 `noise_standard_deviation: 0.1` 为数据添加噪声。最后，用户可以通过 `use_DBSCAN_to_remove_outliers: true` 添加 [DBSCAN](#使用-dbscan-识别离群值) 离群值移除。

!!! note "更多信息可用"
    请查阅 [参数表](freqai-parameter-table.md) 以获取有关这些参数的更多信息。


### 自定义管道

鼓励用户根据自身需求通过构建自己的数据管道来定制数据管道。这只需在 `IFreqaiModel` 的 `train()` 函数内将 `dk.feature_pipeline` 设置为所需的 `Pipeline` 对象即可实现；如果不想改动 `train()` 函数，也可以在 `IFreqaiModel` 中重写 `define_data_pipeline`/`define_label_pipeline` 函数：

!!! note "更多信息可用"
    FreqAI 使用 [`DataSieve`](https://github.com/emergentmethods/datasieve) 管道。它遵循 SKlearn 管道 API，但额外增加了 X、y 和样本权重向量点移除之间的一致性、特征移除、特征名称跟踪等功能。

```python
from datasieve.transforms import SKLearnWrapper, DissimilarityIndex
from datasieve.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer, StandardScaler
from freqai.base_models import BaseRegressionModel


class MyFreqaiModel(BaseRegressionModel):
    """
    某种超酷的自定义模型
    """
    def fit(self, data_dictionary: Dict, dk: FreqaiDataKitchen, **kwargs) -> Any:
        """
        我的自定义拟合函数
        """
        model = cool_model.fit()
        return model

    def define_data_pipeline(self) -> Pipeline:
        """
        用户在此处定义他们的自定义特征管道（如果愿意）
        """
        feature_pipeline = Pipeline([
            ('qt', SKLearnWrapper(QuantileTransformer(output_distribution='normal'))),
            ('di', ds.DissimilarityIndex(di_threshold=1))
        ])

        return feature_pipeline
    
    def define_label_pipeline(self) -> Pipeline:
        """
        用户在此处定义他们的自定义标签管道（如果愿意）
        """
        label_pipeline = Pipeline([
            ('qt', SKLearnWrapper(StandardScaler())),
        ])

        return label_pipeline
```

在此，您正在定义训练和预测期间将用于特征集的精确管道。通过如上所示将其包装在 `SKLearnWrapper` 类中，您可以使用 *大多数* SKLearn 转换步骤。此外，您还可以使用 [`DataSieve` 库](https://github.com/emergentmethods/datasieve) 中提供的任何转换。

通过创建一个继承自 datasieve `BaseTransform` 的类并实现您的 `fit()`、`transform()` 和 `inverse_transform()` 方法，您可以轻松添加自己的转换：

```python
from datasieve.transforms.base_transform import BaseTransform
# 导入您需要的任何其他模块

class MyCoolTransform(BaseTransform):
    def __init__(self, **kwargs):
        self.param1 = kwargs.get('param1', 1)

    def fit(self, X, y=None, sample_weight=None, feature_list=None, **kwargs):
        # 处理 X, y, sample_weight, 或者是 feature_list
        return X, y, sample_weight, feature_list

    def transform(self, X, y=None, sample_weight=None,
                  feature_list=None, outlier_check=False, **kwargs):
        # 处理 X, y, sample_weight, 或者是 feature_list
        return X, y, sample_weight, feature_list

    def inverse_transform(self, X, y=None, sample_weight=None, feature_list=None, **kwargs):
        # 处理 (或不处理) X, y, sample_weight, 或者是 feature_list
        return X, y, sample_weight, feature_list
```

!!! note "提示"
    您可以在与 `IFreqaiModel` 相同的文件中定义此自定义类。

### 将自定义 `IFreqaiModel` 迁移到新管道

如果您创建了带有自定义 `train()`/`predict()` 函数的自定义 `IFreqaiModel`，*并且* 您仍然依赖 `data_cleaning_train/predict()`，那么您需要迁移到新管道。如果您的模型 *不* 依赖 `data_cleaning_train/predict()`，则无需担心此迁移。

有关迁移的更多详细信息可以在 [此处](策略迁移指南.md#freqai-新数据管道) 找到。

## 离群值检测 (Outlier detection)

股票和加密货币市场遭受着大量呈离群数据点形式的无模式噪声的困扰。FreqAI 实施了多种方法来识别此类离群值，从而降低风险。

### 使用差异指数 (DI) 识别离群值

差异指数 (DI) 旨在量化与模型所做出的每个预测相关的关联不确定性。

通过在配置中包含以下语句，可以告诉 FreqAI 使用 DI 从训练/测试数据集中移除离群数据点：

```json
    "freqai": {
        "feature_parameters" : {
            "DI_threshold": 1
        }
    }
```

这将在您的 `feature_pipeline` 中添加 `DissimilarityIndex` 步骤，并将阈值设为 1。DI 允许因不确定性水平过低而抛出离群值（不存在于模型特征空间中）的预测。为此，FreqAI 测量每个训练数据点（特征向量）$X_{a}$ 与所有其他训练数据点之间的距离：

$$ d_{ab} = \sqrt{\sum_{j=1}^p(X_{a,j}-X_{b,j})^2} $$

其中 $d_{ab}$ 是归一化点 $a$ 和 $b$ 之间的距离，$p$ 是特征数量，即向量 $X$ 的长度。一组训练数据点的特征距离 $\overline{d}$ 只是平均距离的平均值：

$$ \overline{d} = \sum_{a=1}^n(\sum_{b=1}^n(d_{ab}/n)/n) $$

$\overline{d}$ 量化了训练数据的离散程度，将其与新预测特征向量 $X_k$ 与所有训练数据之间的距离进行比较：

$$ d_k = \arg \min d_{k,i} $$

这使得差异指数的估算成为可能：

$$ DI_k = d_k/\overline{d} $$

您可以通过 `DI_threshold` 调整 DI 以增加或减少训练模型的推断。较高的 `DI_threshold` 意味着 DI 更加宽松，允许使用远离训练数据的预测；而较低的 `DI_threshold` 则有相反的效果，因此会丢弃更多的预测。

下图描述了一个 3D 数据集的 DI。

![DI](../assets/freqai_DI.jpg)

### 使用支持向量机 (SVM) 识别离群值

通过在配置中包含以下语句，可以告诉 FreqAI 使用支持向量机 (SVM) 从训练/测试数据集中移除离群数据点：

```json
    "freqai": {
        "feature_parameters" : {
            "use_SVM_to_remove_outliers": true
        }
    }
```

这将在您的 `feature_pipeline` 中添加 `SVMOutlierExtractor` 步骤。SVM 将在训练数据上进行训练，任何被 SVM 认定为超出特征空间的数据点都将被移除。

您可以选择通过配置中的 `feature_parameters.svm_params` 字典为 SVM 提供额外参数，例如 `shuffle` 和 `nu`。

参数 `shuffle` 默认设置为 `False` 以确保结果的一致性。如果将其设为 `True`，由于 `max_iter` 较低导致算法无法达到要求的 `tol`，同一数据集多次运行 SVM 可能会得到不同的结果。增加 `max_iter` 可以解决此问题，但会导致处理时间变长。

参数 `nu`（极其广义地说）是应被视为离群值的数据点数量，取值应在 0 到 1 之间。

### 使用 DBSCAN 识别离群值

通过在配置中激活 `use_DBSCAN_to_remove_outliers`，可以配置 FreqAI 使用 DBSCAN 对训练/测试数据集中的离群值或预测中传入的离群值进行聚类和移除：

```json
    "freqai": {
        "feature_parameters" : {
            "use_DBSCAN_to_remove_outliers": true
        }
    }
```

这将在您的 `feature_pipeline` 中添加 `DataSieveDBSCAN` 步骤。这是一种无监督机器学习算法，可以在不知道应该有多少个类簇的情况下对数据进行聚类。

给定若干数据点 $N$ 和距离 $\varepsilon$，DBSCAN 通过将所有在 $\varepsilon$ 距离内拥有 $N-1$ 个其他数据点的数据点设为 *核心点 (core points)* 来对数据集进行聚类。在核心点 $\varepsilon$ 距离内但自身在该距离内不包含 $N-1$ 个其他数据点的数据点被视为 *边缘点 (edge point)*。随后，类簇就是核心点和边缘点的集合。在深度 $<\varepsilon$ 处没有其他数据点的数据点被视为离群值。下图显示了一个 $N = 3$ 的类簇。

![dbscan](../assets/freqai_dbscan.jpg)

FreqAI 使用 `sklearn.cluster.DBSCAN`（详细信息可在 scikit-learn 网页 [此处](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html) (外部网站) 找到），其中 `min_samples` ($N$) 取为特征集中时间点（K 线）数量的 1/4。`eps` ($\varepsilon$) 会自动计算，它是根据特征集中所有数据点成对距离中的最近邻计算出的 *k-距离图 (k-distance graph)* 中的拐点 (elbow point)。


### 使用主成分分析进行数据降维

可以通过在配置中激活 `principal_component_analysis` 来减少特征的维度：

```json
    "freqai": {
        "feature_parameters" : {
            "principal_component_analysis": true
        }
    }
```

这将对特征执行 PCA 并降低其维度，使得数据集的解释方差 (explained variance) >= 0.999。降低数据维度可以提高模型的训练速度，从而允许使用更及时的模型。

---

原始文件来源: [docs/freqai-feature-engineering.md](docs/freqai-feature-engineering.md)
