# 运行 FreqAI (Running FreqAI)

训练和部署自适应机器学习模型有两种方式：实盘部署和历史回测。在两种情况下，FreqAI 都会运行/模拟模型的定期重新训练，如下图所示：

![freqai-window](../assets/freqai_moving-window.jpg)

## 实盘部署 (Live deployments)

FreqAI 可以使用以下命令进行干跑/实盘运行：

```bash
freqtrade trade --strategy FreqaiExampleStrategy --config config_freqai.example.json --freqaimodel LightGBMRegressor
```

启动后，FreqAI 将根据配置设置开始训练一个带有新 `identifier` (标识符) 的新模型。训练完成后，该模型将用于对传入的 K 线进行预测，直到有新模型可用。新模型通常会尽可能频繁地生成，FreqAI 会管理一个内部交易对队列，试图保持所有模型的所有币种都同等更新。FreqAI 始终使用最新训练的模型对传入的实时数据进行预测。如果您不希望 FreqAI 尽可能频繁地重新训练新模型，可以设置 `live_retrain_hours` 来告诉 FreqAI 在训练新模型之前至少等待这么多小时。此外，您可以设置 `expired_hours` 来告诉 FreqAI 避免基于超过该小时数的旧模型进行预测。

默认情况下，训练好的模型会保存到磁盘，以便在回测期间或崩溃后重用。您可以通过在配置中设置 `"purge_old_models": true` 来选择 [清除旧模型数据](#清除旧模型数据) 以节省磁盘空间。

要从保存的回测模型（或之前崩溃的干跑/实盘会话）启动干跑/实盘运行，您只需指定特定模型的 `identifier`：

```json
    "freqai": {
        "identifier": "example",
        "live_retrain_hours": 0.5
    }
```

在这种情况下，尽管 FreqAI 会使用预训练模型启动，但它仍会检查距离模型训练完成已经过去了多少时间。如果加载模型结束时间已经过去了完整的 `live_retrain_hours`，FreqAI 将开始训练一个新模型。

### 自动数据下载

FreqAI 会自动下载所需的数据量，以确保通过定义的 `train_period_days` 和 `startup_candle_count` 完成模型训练（有关这些参数的详细说明，请参见 [参数表](freqai-参数表.md)）。

### 保存预测数据

在特定 `identifier` 模型的生命周期内做出的所有预测都存储在 `historic_predictions.pkl` 中，以便在崩溃或更改配置后重新加载。

### 清除旧模型数据

FreqAI 在每次成功训练后都会存储新的模型文件。随着为适应新市场条件而生成的更先进模型的出现，这些旧文件会变得过时。如果您打算在高频重新训练的情况下长时间运行 FreqAI，应在配置中启用 `purge_old_models`：

```json
    "freqai": {
        "purge_old_models": 4,
    }
```

这将自动清除除最近训练的四个模型之外的所有旧模型，以节省磁盘空间。输入 "0" 则永远不会清除任何模型。

## 回测 (Backtesting)

FreqAI 回测模块可以通过以下命令执行：

```bash
freqtrade backtesting --strategy FreqaiExampleStrategy --strategy-path freqtrade/templates --config config_examples/config_freqai.example.json --freqaimodel LightGBMRegressor --timerange 20210501-20210701
```

如果从未配合现有的配置文件执行过此命令，FreqAI 将为 `--timerange` 展开范围内的每个窗口、每个交易对训练一个新模型。

回测模式要求在部署前 [下载必要的数据](#下载数据以覆盖完整回测期)（这与干跑/实盘模式不同，后者由 FreqAI 自动处理数据下载）。您应仔细考虑下载数据的时间范围必须长于回测时间范围。这是因为 FreqAI 需要在所需的回测时间范围之前的数据来训练模型，以便为设定回测时间范围的第一根 K 线做好预测准备。关于如何计算下载数据的更多细节可以在 [此处](#决定滑动训练窗口的大小和回测时长) 找到。

!!! Note "模型重用"
    一旦训练完成，您可以配合相同的配置文件再次执行回测，FreqAI 将找到已训练的模型并加载它们，而不是花费时间进行训练。如果您想微调（甚至 hyperopt）策略内部的买入和卖出标准，这非常有用。如果您 *想* 配合相同的配置文件重新训练新模型，只需更改 `identifier` 即可。这样，您只需通过指定 `identifier` 即可返回使用任何您想要的模型。

!!! Note
    回测会针对每个回测窗口调用一次 `set_freqai_targets()`（其中窗口数量是完整回测时间范围除以 `backtest_period_days` 参数）。这样做意味着目标模拟了无未来偏差的干跑/实盘行为。然而，`feature_engineering_*()` 中特征的定义是在整个训练时间范围上执行一次的。这意味着您应确保特征不会“偷看”未来。
    关于未来偏差的更多细节可以在 [常见错误](策略自定义.md#开发策略时的常见错误) 中找到。

---

### 保存回测预测数据

为了允许微调您的策略（**不是**特征！），FreqAI 将在回测期间自动保存预测结果，以便它们可以被后续回测和使用相同 `identifier` 模型的实盘运行重用。这提供了一项旨在实现对进场/离场标准的 **高层 hyperopt (优化)** 的性能增强。

在 `unique-id` 文件夹中将创建一个名为 `backtesting_predictions` 的额外目录，其中包含所有以 `feather` 格式存储的预测。

要更改您的 **特征**，您 **必须** 在配置中设置一个新的 `identifier` 以信号通知 FreqAI 训练新模型。

要保存特定回测期间生成的模型，以便您可以从其中之一启动实盘部署而不是训练新模型，您必须在配置中将 `save_backtest_models` 设置为 `True`。

!!! Note
    为了确保模型可以重用，FreqAI 将配合长度为 1 的 dataframe 调用您的策略。如果您的策略需要比这更多的数据来生成相同的特征，则无法在实盘部署中重用回测预测，并且需要为每个新回测更新您的 `identifier`。

### 回测实盘收集的预测数据

FreqAI 允许您通过回测参数 `--freqai-backtest-live-models` 重用实盘历史预测。当您想重用在干跑/实盘中生成的预测进行对比或其他研究时，这非常有用。

不必提供 `--timerange` 参数，因为它会自动通过历史预测文件中的数据计算得出。

### 下载数据以覆盖完整回测期

对于实盘/干跑部署，FreqAI 会自动下载必要的数据。但是，要使用回测功能，您需要手动使用 `download-data` 下载必要的数据（详情见 [此处](数据下载.md#下载数据)）。您需要仔细理解需要下载多少 *额外* 数据，以确保在回测时间范围开始 *之前* 有足够的训练数据。额外数据的量可以通过将起始日期从所需回测时间范围的开头向后移动 `train_period_days` 和 `startup_candle_count`（有关这些参数的详细说明，请参见 [参数表](freqai-参数表.md)）来粗略估算。

例如，要对 `--timerange 20210501-20210701` 进行回测，使用 [示例配置](freqai-配置.md#设置配置文件) 将 `train_period_days` 设为 30，再加上最大 `include_timeframes` 为 1h 下的 `startup_candle_count: 40`，则下载数据的起始日期需要是 `20210501` - 30天 - 40 * 1h / 24小时 = 20210330（即比所需训练时间范围的开始早 31.7 天）。

### 决定滑动训练窗口的大小和回测时长

回测时间范围是通过配置文件中典型的 `--timerange` 参数定义的。滑动训练窗口的时长由 `train_period_days` 设置，而 `backtest_period_days` 是滑动回测窗口，两者均以天数为单位（`backtest_period_days` 可以是浮点数，以表示干跑/实盘模式下的日内重新训练）。在 [示例配置](freqai-配置.md#设置配置文件)（可见于 `config_examples/config_freqai.example.json`）中，用户要求 FreqAI 使用 30 天的训练周期并在后续的 7 天上进行回测。模型训练完成后，FreqAI 将回测随后的 7 天。随后“滑动窗口”向前移动一周（模拟实盘模式下 FreqAI 每周重新训练一次），新模型使用之前的 30 天（包含前一个模型用于回测的 7 天）进行训练。这一过程在 `--timerange` 结束前循环往复。这意味着如果您设置 `--timerange 20210501-20210701`，FreqAI 在时间范围结束时将一共训练过 8 个独立的模型（因为完整的范围涵盖了 8 周）。

!!! Note
    虽然允许设置小数形式的 `backtest_period_days`，但您应当意识到 `--timerange` 将被该值相除以确定 FreqAI 为回测完整范围而需要训练的模型数量。例如，通过设置 10 天的 `--timerange` 和 0.1 的 `backtest_period_days`，FreqAI 将需要为每个交易对训练 100 个模型才能完成完整回测。正因如此，对 FreqAI 自适应训练进行真正的完整回测将耗费 *极长* 的时间。全面测试模型的最佳方式是干跑运行并让其不断进行训练。在这种情况下，回测所需的时间将与干跑完全相同。

## 定义模型过期 (Model expirations)

在干跑/实盘模式下，FreqAI 会按顺序训练每个交易对（在与主 Freqtrade 机器人分离的线程/GPU 上）。这意味着模型之间始终存在年龄差异。如果您在训练 50 个交易对，且每个对需要 5 分钟来训练，那么最旧的模型将超过 4 小时前。如果策略的特征时间尺度（交易时长目标）小于 4 小时，这可能是不可接受的。您可以通过在配置文件中设置 `expiration_hours`，决定仅在模型年龄小于特定小时数时才进行交易进场：

```json
    "freqai": {
        "expiration_hours": 0.5,
    }
```

在给出的示例配置中，用户仅允许基于年龄小于半小时的模型进行预测。

## 控制模型学习过程

模型训练参数对于所选的机器学习库是唯一的。FreqAI 允许通过配置中的 `model_training_parameters` 字典为任何库设置任何参数。示例配置（位于 `config_examples/config_freqai.example.json`）展示了部分与 `Catboost` 和 `LightGBM` 相关的示例参数，但您可以添加这些库中可用的任何参数，或者您选择实现的任何其他机器学习库的参数。

数据拆分参数定义在 `data_split_parameters` 中，可以是任何与 scikit-learn 的 `train_test_split()` 函数相关的参数。`train_test_split()` 拥有一个名为 `shuffle` 的参数，允许对数据进行洗牌或保持不洗牌。这对于避免使用具有时间自动相关性的数据造成训练偏差特别有用。关于这些参数的更多细节可以在 [scikit-learn 网站](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html) (外部网站) 找到。

FreqAI 特定参数 `label_period_candles` 定义了用于 `labels` 的偏移量（未来 K 线数量）。在给出的 [示例配置](freqai-配置.md#设置配置文件) 中，用户要求标签基于未来的 24 根 K 线。

## 持续学习 (Continual learning)

您可以通过在配置中设置 `"continual_learning": true` 来选择采用持续学习方案。通过启用 `continual_learning`，在从头训练初始模型后，后续的训练将从前一次训练的最终模型状态开始。这使得新模型对之前的状态具有“记忆”。默认情况下，此项设为 `False`，这意味着所有新模型都是从头训练的，不受之前模型的影响。

???+ danger "持续学习强制要求恒定的参数空间"
    由于 `continual_learning` 意味着模型参数空间在训练之间 *不能* 改变，因此启用 `continual_learning` 时会自动禁用 `principal_component_analysis` (主成分分析)。提示：PCA 会改变参数空间和特征数量，关于 PCA 的更多信息见 [此处](freqai-特征工程.md#使用主成分分析进行数据降维)。

???+ danger "实验性功能"
    请注意，这目前是一种简单的增量学习方法，当市场偏离您的模型时，极有可能出现过拟合或陷入局部最小值。我们在 FreqAI 中提供这些机制主要用于实验目的，并为在加密市场等混乱系统中使用更成熟的持续学习方法做好准备。

## Hyperopt (参数优化)

您可以使用与 [典型的 Freqtrade hyperopt](hyperopt.md) 相同的命令进行 hyperopt：

```bash
freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --strategy FreqaiExampleStrategy --freqaimodel LightGBMRegressor --strategy-path freqtrade/templates --config config_examples/config_freqai.example.json --timerange 20220428-20220507
```

`hyperopt` 要求您以与执行 [回测](#回测) 相同的方式预先下载数据。此外，尝试 hyperopt FreqAI 策略时，必须考虑一些限制：

- `--analyze-per-epoch` hyperopt 参数与 FreqAI 不兼容。
- 无法 hyperopt `feature_engineering_*()` 和 `set_freqai_targets()` 函数中的指标。这意味着您无法使用 hyperopt 优化模型参数（特征创建过程）。除此例外，可以优化所有其他 [搜索空间](hyperopt.md#使用更小的搜索空间运行-hyperopt)。
- 回测的操作指南同样适用于 hyperopt。

将 hyperopt 与 FreqAI 结合的最佳方法是专注于 hyperopt 进场/离场阈值/标准。您需要关注那些没有用于特征生成的参数。例如，您不应尝试优化特征创建过程中的滚动窗口长度，或者 FreqAI 配置中任何会改变预测的部分。为了高效地对 FreqAI 策略进行 hyperopt，FreqAI 将预测结果存储为 dataframe 并重用它们。因此要求仅 hyperopt 进场/离场阈值/标准。

FreqAI 中一个良好的可 hyperopt 参数示例是 [差异指数 (DI)](freqai-特征工程.md#使用差异指数-di-识别离群值) `DI_values` 的阈值，超过该阈值我们认为数据点是离群值：

```python
di_max = IntParameter(low=1, high=20, default=10, space='buy', optimize=True, load=True)
dataframe['outlier'] = np.where(dataframe['DI_values'] > self.di_max.value/10, 1, 0)
```

这个特定的 hyperopt 将帮助您理解适合您特定参数空间的 `DI_values`。

## 使用 Tensorboard

!!! note "可用性"
    FreqAI 为多种模型包含了 Tensorboard 支持，包括 XGBoost、所有 PyTorch 模型、强化学习以及 Catboost。如果您想看到 Tensorboard 集成到另一种模型类型中，请在 [Freqtrade GitHub](https://github.com/freqtrade/freqtrade/issues) 上提交 issue。

!!! danger "环境要求"
    Tensorboard 日志记录需要安装 FreqAI 的 Torch 版本或使用对应的 Docker 镜像。


使用 Tensorboard 最简单的方法是确保配置文件中 `freqai.activate_tensorboard` 设置为 `True`（默认设置），运行 FreqAI，然后打开另一个 shell 运行：

```bash
cd freqtrade
tensorboard --logdir user_data/models/unique-id
```

其中 `unique-id` 是在 `freqai` 配置文件中设置的 `identifier`。如果您希望在浏览器中访问 127.0.0.1:6060（6060 是 Tensorboard 使用的默认端口）查看输出，则此命令必须在单独的 shell 中运行。

![tensorboard](../assets/tensorboard.jpg)


!!! note "为提高性能而禁用"
    Tensorboard 日志记录可能会减慢训练速度，在实盘生产环境中使用时应将其禁用。

---

原始文件来源: [docs/freqai-running.md](docs/freqai-running.md)
