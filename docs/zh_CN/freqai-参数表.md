# 参数表 (Parameter Table)

下表列出了 FreqAI 可用的所有配置参数。部分参数在 `config_examples/config_freqai.example.json` 中有示例。

必填参数标记为 **必选 (Required)**，必须以建议的方式之一进行设置。

### 通用配置参数 (General configuration parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **`config.freqai` 树下的通用配置参数**
| `freqai` | **必选。** <br> 包含控制 FreqAI 所有参数的父级字典。 <br> **数据类型：** 字典 (Dictionary)。
| `train_period_days` | **必选。** <br> 用于训练数据的天数（滑动窗口的宽度）。 <br> **数据类型：** 正整数。
| `backtest_period_days` | **必选。** <br> 在回测期间，在滑动上述定义的 `train_period_days` 窗口并重新训练模型之前，从训练好的模型中进行推断的天数（详见 [此处](freqai-running.md#backtesting)）。这可以是小数天数，但请注意，提供的 `timerange` 将被该数字相除，从而产生完成回测所需的训练次数。 <br> **数据类型：** 浮点数。
| `identifier` | **必选。** <br> 当前模型的唯一 ID。如果模型保存到磁盘，`identifier` 允许重新加载特定的预训练模型/数据。 <br> **数据类型：** 字符串。
| `live_retrain_hours` | 干跑/实盘运行期间重新训练的频率。 <br> **数据类型：** 浮点数 > 0。 <br> 默认值：`0`（模型尽可能频繁地重新训练）。
| `expiration_hours` | 如果模型超过 `expiration_hours` 小时，则避免进行预测。 <br> **数据类型：** 正整数。 <br> 默认值：`0`（模型永不过期）。
| `purge_old_models` | 磁盘上保留的模型数量（与回测无关）。默认值为 2，这意味着干跑/实盘运行将在磁盘上保留最新的 2 个模型。设置为 0 则保留所有模型。为了保持向后兼容性，此参数也接受布尔值。 <br> **数据类型：** 整数。 <br> 默认值：`2`。
| `save_backtest_models` | 运行回测时将模型保存到磁盘。回测通过保存预测数据并直接在后续运行中重用它们（当您希望调整进场/离场参数时）能最有效地操作。将回测模型保存到磁盘还允许使用相同的模型文件来启动具有相同模型 `identifier` 的干跑/实盘实例。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`（不保存模型）。
| `fit_live_predictions_candles` | 用于从预测数据（而非训练数据集）计算目标（标签）统计数据的历史 K 线数量（更多信息见 [此处](freqai-配置.md#创建动态目标阈值)）。 <br> **数据类型：** 正整数。
| `continual_learning` | 使用最近训练模型的最终状态作为新模型的起点，从而实现增量学习（更多信息见 [此处](freqai-running.md#continual-learning)）。请注意，这目前是一种简单的增量学习方法，当市场偏离您的模型时，极有可能出现过拟合或陷入局部最小值。我们在此提供接口主要用于实验目的，并为在加密市场等混乱系统中使用更成熟的持续学习方法做好准备。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `write_metrics_to_disk` | 在 json 文件中收集训练耗时、推断耗时和 CPU 使用率。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `data_kitchen_thread_count` | <br> 指定用于数据处理（离群值方法、归一化等）的线程数。这不会影响用于训练的线程数。如果用户未设置（默认），FreqAI 将使用最大线程数 - 2（为 Freqtrade 机器人和 FreqUI 留出 1 个物理核心）。 <br> **数据类型：** 正整数。
| `activate_tensorboard` | <br> 指示是否为支持 Tensorboard 的模块（目前包括强化学习、XGBoost、Catboost 和 PyTorch）激活 Tensorboard。Tensorboard 需要安装 Torch，这意味着您将需要 torch/RL Docker 镜像，或者需要在安装提示关于是否安装 Torch 时回答“yes”。 <br> **数据类型：** 布尔值。 <br> 默认值：`True`。
| `wait_for_training_iteration_on_reload` | <br> 使用 `/reload` 或 `ctrl-c` 时，在完成平滑停机前等待当前训练迭代完成。如果设为 `False`，FreqAI 将中断当前训练迭代，使您能更快地平滑停机，但您会丢失当前的训练迭代进度。 <br> **数据类型：** 布尔值。 <br> 默认值：`True`。

### 特征参数 (Feature parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **`freqai.feature_parameters` 子字典下的特征参数**
| `feature_parameters` | 包含用于设计特征集的参数的字典。详情和示例请见 [此处](freqai-特征工程.md)。 <br> **数据类型：** 字典。
| `include_timeframes` | 一个时间范围列表，`feature_engineering_expand_*()` 中的所有指标都将针对这些时间范围创建。该列表作为特征添加到基础指标数据集中。 <br> **数据类型：** 时间范围列表（字符串）。
| `include_corr_pairlist` | 一个相关币种列表，FreqAI 将作为额外特征添加到 `pair_whitelist` 中的所有币种中。在特征工程期间（详见 [此处](freqai-特征工程.md)），将为每个相关币种创建在 `feature_engineering_expand_*()` 中设置的所有指标。相关币种特征被添加到基础指标数据集中。 <br> **数据类型：** 资产列表（字符串）。
| `label_period_candles` | 为其创建标签的未来 K 线数量。这可以用于 `set_freqai_targets()`（详见 `templates/FreqaiExampleStrategy.py` 的用法）。此参数并非强制必选，您可以创建自定义标签并选择是否使用此参数。请参阅 `templates/FreqaiExampleStrategy.py` 查看示例用法。 <br> **数据类型：** 正整数。
| `include_shifted_candles` | 将前几根 K 线的特征添加到后续 K 线中，意图添加历史信息。如果使用，FreqAI 将复制并平移来自 `include_shifted_candles` 根前序 K 线的所有特征，以便后续 K 线可以使用这些信息。 <br> **数据类型：** 正整数。
| `weight_factor` | 根据数据点的近期程度为其赋予权重（详见 [此处](freqai-特征工程.md#针对时间重要性设置特征权重)）。 <br> **数据类型：** 正浮点数（通常 < 1）。
| `indicator_max_period_candles` | **不再使用 (#7325)**。 由在 [策略](freqai-配置.md#构建-freqai-策略) 中设置的 `startup_candle_count` 取代。`startup_candle_count` 与时间范围无关，定义了 `feature_engineering_*()` 中用于创建指标的最大 *周期 (period)*。FreqAI 使用此参数连同 `include_time_frames` 中的最大时间范围来计算需要下载多少数据点，从而使第一个数据点不包含 NaN。 <br> **数据类型：** 正整数。
| `indicator_periods_candles` | 计算指标的时间周期。这些指标被添加到基础指标数据集中。 <br> **数据类型：** 正整数列表。
| `principal_component_analysis` | 使用主成分分析自动降低数据集的维度。详见其工作原理 [此处](freqai-特征工程.md#使用主成分分析进行数据降维)。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `plot_feature_importances` | 为每个模型创建前/后 `plot_feature_importances` 个特征的特征重要性图表。图表存储在 `user_data/models/<identifier>/sub-train-<COIN>_<timestamp>.html`。 <br> **数据类型：** 整数。 <br> 默认值：`0`。
| `DI_threshold` | 设置为 > 0 时激活差异指数 (Dissimilarity Index) 用于离群值检测。详见其工作原理 [此处](freqai-特征工程.md#使用差异指数-di-识别离群值)。 <br> **数据类型：** 正浮点数（通常 < 1）。
| `use_SVM_to_remove_outliers` | 训练支持向量机 (SVM) 来检测并从训练数据集以及传入的数据点中移除离群值。详见其工作原理 [此处](freqai-特征工程.md#使用支持向量机-svm-识别离群值)。 <br> **数据类型：** 布尔值。
| `svm_params` | Sklearn `SGDOneClassSVM()` 中可用的所有参数。详见部分精选参数 [此处](freqai-特征工程.md#使用支持向量机-svm-识别离群值)。 <br> **数据类型：** 字典。
| `use_DBSCAN_to_remove_outliers` | 使用 DBSCAN 算法对数据进行聚类，以识别并从训练和预测数据中移除离群值。详见其工作原理 [此处](freqai-特征工程.md#使用-dbscan-识别离群值)。 <br> **数据类型：** 布尔值。
| `noise_standard_deviation` | 如果设置，FreqAI 会向训练特征添加噪声，旨在防止过拟合。FreqAI 从标准差为 `noise_standard_deviation` 的高斯分布中生成随机偏差，并将其添加到所有数据点。`noise_standard_deviation` 应保持相对于归一化空间的比例，即在 -1 和 1 之间。换句话说，由于 FreqAI 中的数据总是归一化到 -1 和 1 之间，因此 `noise_standard_deviation: 0.05` 将导致 32% 的数据随机增加/减少超过 2.5%（即落入第一个标准差内的数据百分比）。 <br> **数据类型：** 整数。 <br> 默认值：`0`。
| `outlier_protection_percentage` | 启用此项可防止离群值检测方法丢弃过多数据。如果超过 `outlier_protection_percentage` % 的点被 SVM 或 DBSCAN 检测为离群值，FreqAI 将记录一条警告消息并忽略离群值检测，即保留原始数据集完整无缺。如果触发了离群值保护，则不会基于训练数据集生成预测。 <br> **数据类型：** 浮点数。 <br> 默认值：`30`。
| `reverse_train_test_order` | 拆分特征数据集（见下文），并使用最新的数据拆分进行训练，并在数据的历史拆分上进行测试。这允许模型训练到最近的数据点，同时避免过拟合。但是，在使用此参数之前，应仔细理解其非传统性质。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`（不反转）。
| `shuffle_after_split` | 将数据拆分为训练集和测试集，然后分别对两组数据进行洗牌。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `buffer_train_data_candles` | 在填充指标 *之后*，从训练数据的开头和结尾切除 `buffer_train_data_candles` 数量的 K 线。主要应用示例是预测极大值和极小值时，`argrelextrema` 函数无法知道时间范围边缘的极大值/极小值。为了提高模型准确性，最好在完整时间范围内计算 `argrelextrema`，然后使用此函数按照核 (kernel) 切除边缘（缓冲区）。在另一种情况下，如果目标设置为平移后的价格波动，此缓冲区是不必要的，因为时间范围末尾的平移 K 线将是 NaN，FreqAI 会自动从训练数据集中将其切除。<br> **数据类型：** 整数。 <br> 默认值：`0`。

### 数据拆分参数 (Data split parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **`freqai.data_split_parameters` 子字典下的数据拆分参数**
| `data_split_parameters` | 包含来自 scikit-learn `test_train_split()` 的任何额外可用参数，详见 [此处](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html) (外部网站)。 <br> **数据类型：** 字典。
| `test_size` | 应用于测试而非训练的数据比例。 <br> **数据类型：** 0 到 1 之间的正浮点数。
| `shuffle` | 训练期间对训练数据点进行洗牌。通常为了不破坏时间序列预测中数据的年代顺序，此项设为 `False`。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。

### 模型训练参数 (Model training parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **`freqai.model_training_parameters` 子字典下的模型训练参数**
| `model_training_parameters` | 一个灵活的字典，包含所选模型库提供的所有参数。例如，如果您使用 `LightGBMRegressor`，此字典可以包含 [此处](https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMRegressor.html) (外部网站) 提供的 `LightGBMRegressor` 的任何参数。如果您选择了不同的模型，此字典可以包含该模型的任何参数。当前可用模型列表可在 [此处](freqai-配置.md#使用不同的预测模型) 找到。 <br> **数据类型：** 字典。
| `n_estimators` | 模型训练中拟合的提升树数量。 <br> **数据类型：** 整数。
| `learning_rate` | 模型训练期间的提升学习率。 <br> **数据类型：** 浮点数。
| `n_jobs`, `thread_count`, `task_type` | 设置并行处理的线程数和 `task_type`（`gpu` 或 `cpu`）。不同的模型库使用不同的参数名称。 <br> **数据类型：** 浮点数。

### 强化学习参数 (Reinforcement Learning parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **`freqai.rl_config` 子字典下的强化学习参数**
| `rl_config` | 一个包含强化学习模型控制参数的字典。 <br> **数据类型：** 字典。
| `train_cycles` | 训练步数将基于 `train_cycles * 训练数据点数量` 来设置。 <br> **数据类型：** 整数。
| `max_trade_duration_candles`| 指导代理训练以保持交易在所需的长度以下。示例用法展示在 `prediction_models/ReinforcementLearner.py` 中可自定义的 `calculate_reward()` 函数内。 <br> **数据类型：** int。
| `model_type` | 来自 `stable_baselines3` 或 `SBcontrib` 的模型字符串。可用字符串包括：`'TRPO', 'ARS', 'RecurrentPPO', 'MaskablePPO', 'PPO', 'A2C', 'DQN'`。用户应访问其文档以确保 `model_training_parameters` 与对应的 `stable_baselines3` 模型可用参数匹配。[PPO 文档](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html) (外部网站) <br> **数据类型：** 字符串。
| `policy_type` | `stable_baselines3` 中可用的策略类型之一。 <br> **数据类型：** 字符串。
| `max_training_drawdown_pct` | 代理在训练期间允许体验的最大回撤。 <br> **数据类型：** 浮点数。 <br> 默认值：0.8。
| `cpu_count` | 专门用于强化学习训练过程的线程/CPU 数量（取决于是否选择了 `ReinforcementLearner_multiproc`）。建议不要触动此项，默认情况下，此值设置为物理核心总数减 1。 <br> **数据类型：** int。
| `model_reward_parameters` | `ReinforcementLearner.py` 中可自定义的 `calculate_reward()` 函数内使用的参数。 <br> **数据类型：** int。
| `add_state_info` | 告诉 FreqAI 在特征集中包含用于训练和推断的状态信息。当前状态变量包括交易时长、当前利润、交易仓位。这仅在干跑/实盘运行中可用，回测时会自动切换为 false。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `net_arch` | 网络架构，在 [`stable_baselines3` 文档](https://stable-baselines3.readthedocs.io/en/master/guide/custom_policy.html#examples) 中有详尽描述。概括为：`[<共享层>, dict(vf=[<非共享价值网络层>], pi=[<非共享策略网络层>])]`。默认设置为 `[128, 128]`，定义了 2 个各有 128 个单元的共享隐藏层。
| `randomize_starting_position` | 随机化每个回合 (episode) 的起点以避免过拟合。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `drop_ohlc_from_features` | 在训练期间传递给代理的特征集中不包含归一化的 OHLC 数据（在所有情况下 OHLC 仍将用于驱动环境）。 <br> **数据类型：** 布尔值。 <br> **默认值：** `False`。
| `progress_bar` | 显示一个包含当前进度、已用时间和预估剩余时间的进度条。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。

### PyTorch 参数 (PyTorch parameters)

#### 通用 (general)

| 参数 | 描述 |
|------------|-------------|
|  |  **`freqai.model_training_parameters` 子字典下的模型训练参数**
| `learning_rate` | 要传递给优化器 (optimizer) 的学习率。 <br> **数据类型：** 浮点数。 <br> 默认值：`3e-4`。
| `model_kwargs` | 要传递给模型类的参数。 <br> **数据类型：** 字典。 <br> 默认值：`{}`。
| `trainer_kwargs` | 要传递给训练器 (trainer) 类的参数。 <br> **数据类型：** 字典。 <br> 默认值：`{}`。

#### trainer_kwargs

| 参数 | 描述 |
|--------------|-------------|
|              |  **`freqai.model_training_parameters.model_kwargs` 子字典下的模型训练参数**
| `n_epochs` | `n_epochs` 参数是 PyTorch 训练循环中的一个关键设置，它决定了整个训练数据集将被用于更新模型参数的次数。一个 epoch 代表对整个训练数据集的一次完整遍历。会覆盖 `n_steps`。必须设置 `n_epochs` 或 `n_steps` 之一。 <br><br> **数据类型：** 整数。可选。 <br> 默认值：`10`。
| `n_steps` | 设置 `n_epochs` 的另一种方式 —— 要运行的训练迭代次数。此处的迭代是指我们调用 `optimizer.step()` 的次数。如果设置了 `n_epochs`，则忽略此项。该函数的简化版本： <br><br> n_epochs = n_steps / (n_obs / batch_size) <br><br> 这里的动机是 `n_steps` 在不同的 `n_obs`（数据点数量）之间更容易优化并保持稳定。 <br> <br> **数据类型：** 整数。可选。 <br> 默认值：`None`。
| `batch_size` | 训练期间使用的 batch 大小。 <br><br> **数据类型：** 整数。 <br> 默认值：`64`。

### 额外参数 (Additional parameters)

| 参数 | 描述 |
|------------|-------------|
|  |  **外部参数**
| `freqai.keras` | 如果所选模型使用了 Keras（对于基于 TensorFlow 的预测模型很常见），则需要激活此标志，以便模型的保存/加载遵循 Keras 标准。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `freqai.conv_width` | 神经网络输入张量的宽度。这通过将历史数据点作为张量的第二维输入，取代了对平移 K 线 (`include_shifted_candles`) 的需求。技术上，此参数也可用于回归器，但它只会增加计算开销，而不会改变模型训练/预测。 <br> **数据类型：** 整数。 <br> 默认值：`2`。
| `freqai.reduce_df_footprint` | 将所有数值列重新转换为 float32/int32，目的是减少 RAM/磁盘使用并缩短训练/推断时间。此参数设置在 Freqtrade 配置文件的主层级（而非 FreqAI 内部）。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。
| `freqai.override_exchange_check` | 覆盖交易所检查，强制 FreqAI 使用历史数据可能不足的交易所。如果您知道您的 FreqAI 模型和策略不需要历史数据，请将其设为 True。 <br> **数据类型：** 布尔值。 <br> 默认值：`False`。

---

原始文件来源: [docs/freqai-parameter-table.md](docs/freqai-parameter-table.md)
