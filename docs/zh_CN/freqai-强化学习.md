# 强化学习 (Reinforcement Learning)

!!! Note "安装占用空间"
    强化学习的依赖包含大型软件包（如 `torch`），应在执行 `./setup.sh -i` 期间针对“您是否还需要 freqai-rl 的依赖项（~700mb 额外空间）[y/N]？”问题回答 "y" 来显式请求安装。
    偏好 Docker 的用户应确保使用以 `_freqairl` 结尾的 Docker 镜像。

## 背景与术语

### 什么是强化学习，为什么 FreqAI 需要它？

强化学习 (Reinforcement Learning, RL) 涉及两个重要组件：*代理 (agent)* 和训练 *环境 (environment)*。在代理训练期间，代理逐根 K 线遍历历史数据，始终从一组动作中做出一个动作：做多进场 (Long entry)、做多离场 (Long exit)、做空进场 (Short entry)、做空离场 (Short exit)、观望 (Neutral)。在此训练过程中，环境会跟踪这些动作的表现，并根据用户自定义的 `calculate_reward()` 函数奖励代理（我们在此提供了一个默认奖励函数，供用户根据需要进行扩展 [详情见此](#创建自定义奖励函数)）。该奖励被用于训练神经网络中的权重。

FreqAI RL 实现的第二个重要组件是 *状态 (state)* 信息的使用。状态信息在每一步都被输入网络，包括当前利润、当前仓位以及当前交易时长。这些信息在训练环境中用于训练代理，并在干跑/实盘中加强代理（此功能在回测中不可用）。*由于这些信息在实盘部署中随时可用，因此 FreqAI + Freqtrade 是这种增强机制的完美组合。*

强化学习是 FreqAI 的必然发展方向，因为它增加了一层分类器 (Classifiers) 和回归器 (Regressors) 无法比拟的适应性和市场反应能力。然而，分类器和回归器拥有 RL 所不具备的优势，例如鲁棒的预测。训练不当的 RL 代理可能会发现一些“作弊”和“窍门”来最大化奖励，而实际上并未赢得任何交易。因此，RL 比典型的分类器和回归器更复杂，需要更高层次的理解。

### RL 接口 (RL interface)

通过当前的框架，我们的目标是通过通用的“预测模型”文件暴露训练环境，该文件是一个用户继承的 `BaseReinforcementLearner` 对象（例如 `freqai/prediction_models/ReinforcementLearner`）。在此用户类中，RL 环境通过 `MyRLEnv` 可用并被定制，如下文 [所示](#创建自定义奖励函数)。

我们设想大多数用户将精力集中在 `calculate_reward()` 函数的创意设计上（[详见此处](#创建自定义奖励函数)），而保持环境的其他部分不动。其他用户可能根本不会改动环境，他们只会玩转配置设置和 FreqAI 中已经存在的强大特征工程。与此同时，我们允许高级用户完全创建自己的模型类。

该框架基于 stable_baselines3 (torch) 和用于基础环境类的 OpenAI gym 构建。但总的来说，模型类被很好地隔离了。因此，竞争库的增加可以很容易地集成到现有框架中。对于环境，它继承自 `gym.Env`，这意味着为了切换到不同的库，必须编写一个全新的环境。

### 重要考量

如上文所述，代理是在一个模拟的交易“环境”中被“训练”的。在我们的例子中，那个环境看起来可能与真实的 Freqtrade 回测环境非常相似，但它 *并非* 如此。事实上，RL 训练环境要简化得多。它并不包含任何复杂的策略逻辑，例如像 `custom_exit`、`custom_stoploss`、杠杆控制等回调。相反，RL 环境是真实市场的一个非常“原生”的展示，代理在那里可以自由学习政策（也就是：止损、止盈等），这些是由 `calculate_reward()` 强制执行的。因此，重要的是要考虑到代理训练环境并不等同于现实世界。

## 运行强化学习

设置并运行强化学习模型与运行回归器或分类器相同。必须在命令行中定义同样的两个标志 `--freqaimodel` 和 `--strategy`：

```bash
freqtrade trade --freqaimodel ReinforcementLearner --strategy MyRLStrategy --config config.json
```

其中 `ReinforcementLearner` 将使用来自 `freqai/prediction_models/ReinforcementLearner` 的模板化 `ReinforcementLearner`（或位于 `user_data/freqaimodels` 中的用户自定义模型）。另一方面，该策略遵循与典型回归器相同的基于 `feature_engineering_*` 的基础 [特征工程](freqai-特征工程.md)。区别在于目标的创建——强化学习不需要目标。然而，FreqAI 需要在 action 列设置一个默认（中性）值：

```python
    def set_freqai_targets(self, dataframe, **kwargs) -> DataFrame:
        """
        *仅适用于启用 FreqAI 的策略*
        必选函数，用于设置模型目标。
        所有目标必须前缀 `&` 才能被 FreqAI 内部识别。

        关于可用特征工程的更多细节：
        https://www.freqtrade.io/en/latest/freqai-feature-engineering

        :param df: 接收目标的策略 dataframe
        使用示例：dataframe["&-target"] = dataframe["close"].shift(-1) / dataframe["close"]
        """
        # 对于 RL，没有直接的目标需要设置。这是在代理发送动作前的填充（中性值）。
        dataframe["&-action"] = 0
        return dataframe
```

大部分函数与典型的回归器保持一致，然而，下面的函数展示了策略必须如何将原始价格数据传递给代理，以便其在训练环境中能够访问原始 OHLCV：

```python
    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        # 强化学习模型需要以下特征
        dataframe[f"%-raw_close"] = dataframe["close"]
        dataframe[f"%-raw_open"] = dataframe["open"]
        dataframe[f"%-raw_high"] = dataframe["high"]
        dataframe[f"%-raw_low"] = dataframe["low"]
    return dataframe
```

最后，不需要显式创建“标签 (label)”——相反，必须分配 `&-action` 列，该列在 `populate_entry/exit_trends()` 中被访问时将包含代理的动作。在当前示例中，中性动作为 0。此值应与所使用的环境一致。FreqAI 提供了两个环境，它们都使用 0 作为中性动作。

在用户意识到不需要设置标签后，他们很快就会明白代理正在做出其“自己的”进场和离场决定。这使得策略构建变得相当简单。进场和离场信号以整数形式来自代理——这些整数被直接用于决定策略中的进场和离场：

```python
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        enter_long_conditions = [df["do_predict"] == 1, df["&-action"] == 1]

        if enter_long_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_long_conditions), ["enter_long", "enter_tag"]
            ] = (1, "long")

        enter_short_conditions = [df["do_predict"] == 1, df["&-action"] == 3]

        if enter_short_conditions:
            df.loc[
                reduce(lambda x, y: x & y, enter_short_conditions), ["enter_short", "enter_tag"]
            ] = (1, "short")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        exit_long_conditions = [df["do_predict"] == 1, df["&-action"] == 2]
        if exit_long_conditions:
            df.loc[reduce(lambda x, y: x & y, exit_long_conditions), "exit_long"] = 1

        exit_short_conditions = [df["do_predict"] == 1, df["&-action"] == 4]
        if exit_short_conditions:
            df.loc[reduce(lambda x, y: x & y, exit_short_conditions), "exit_short"] = 1

        return df
```

重要的是要考虑到 `&-action` 取决于他们选择使用哪种环境。上面的示例展示了 5 种动作，其中 0 是中性，1 是做多进场，2 是做多离场，3 是做空进场，4 是做空离场。

## 配置强化学习器 (Reinforcement Learner)

为了配置 `Reinforcement Learner`，必须在 `freqai` 配置中存在以下字典：

```json
        "rl_config": {
            "train_cycles": 25,
            "add_state_info": true,
            "max_trade_duration_candles": 300,
            "max_training_drawdown_pct": 0.02,
            "cpu_count": 8,
            "model_type": "PPO",
            "policy_type": "MlpPolicy",
            "model_reward_parameters": {
                "rr": 1,
                "profit_aim": 0.025
            }
        }
```

参数细节可以从 [此处](freqai-参数表.md) 找到，但总的来说，`train_cycles` 决定了代理应在其模拟环境中循环遍历 K 线数据以训练模型权重的次数。`model_type` 是一个字符串，用于选择 [stable_baselines](https://stable-baselines3.readthedocs.io/en/master/)(外部链接) 中可用的模型之一。

!!! Note
    如果您想尝试 `continual_learning` (持续学习)，那么应在主 `freqai` 配置字典中将该值设置为 `true`。这将告诉强化学习库从上一个模型的最终状态继续训练新模型，而不是每次启动重新训练时都重头开始。

!!! Note
    请记住，通用的 `model_training_parameters` 字典应包含针对特定 `model_type` 的所有模型超参数定制。例如，`PPO` 参数可以在 [此处](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html) 找到。

## 创建自定义奖励函数

!!! danger "非生产环境使用"
    警告！
    Freqtrade 源代码中提供的奖励函数是功能的展示，旨在展示/测试尽可能多的环境控制特性。它也被设计成可以在小型计算机上快速运行。这只是一个基准测试 (benchmark)，*不* 用于实盘生产环境。请注意，您将需要创建自己的 `custom_reward()` 函数，或使用 Freqtrade 源代码之外其他用户构建的模板。

当您开始修改策略和预测模型时，您很快会意识到强化学习器与回归器/分类器之间的一些重要区别。首先，策略并不会设置目标值（没有标签！）。相反，您在 `MyRLEnv` 类中设置 `calculate_reward()` 函数（见下文）。`prediction_models/ReinforcementLearner.py` 中提供了一个默认的 `calculate_reward()`，用以演示创建奖励所需的必要构建块，但这 *并非* 为生产环境设计。用户 *必须* 创建他们自己的自定义强化学习模型类，或使用来自 Freqtrade 源代码之外的预构建模型，并将其保存到 `user_data/freqaimodels`。正是在 `calculate_reward()` 中，关于市场的创意理论得以表达。例如，当代理完成一笔盈利交易时，您可以奖励它；而当它完成一笔亏损交易时，您可以惩罚它。或者，您可能希望奖励代理进场，而惩罚代理持仓时间过长。下面我们展示了这些奖励是如何计算的示例：

!!! note "提示"
    最好的奖励函数是那些连续可导且缩放良好的函数。换句话说，对一个罕见事件添加一个巨大的负惩罚并不是一个好主意，神经网络将无法学习该函数。相反，对一个常见事件添加一个小额负惩罚会更好，这会帮助代理学得更快。不仅如此，您还可以通过让奖励/惩罚随严重程度按某种线性/指数函数缩放，来帮助提高其连续性。也就是说，随着交易时长的增加，您会缓慢增加惩罚。这比在单一时间点发生一次巨大的惩罚要好。

```python
from freqtrade.freqai.prediction_models.ReinforcementLearner import ReinforcementLearner
from freqtrade.freqai.RL.Base5ActionRLEnv import Actions, Base5ActionRLEnv, Positions


class MyCoolRLModel(ReinforcementLearner):
    """
    用户创建的 RL 预测模型。

    将此文件保存到 `freqtrade/user_data/freqaimodels`

    然后通过以下方式使用：

    freqtrade trade --freqaimodel MyCoolRLModel --config config.json --strategy SomeCoolStrat

    在这里，用户可以重写 `IFreqaiModel` 继承树中提供的任何函数。
    对于 RL 最重要的是，这是用户重写 `MyRLEnv`（见下文）以定义自定义 `calculate_reward()` 函数，
    或重写环境的任何其他部分的地方。

    此类还允许用户重写 IFreqaiModel 树的其他任何部分。
    例如，用户可以重写 `def fit()`、`def train()` 或 `def predict()` 来微调这些过程的控制。

    另一个常见的重写可能是 `def data_cleaning_predict()`，用户可以在其中微调数据处理管道的控制。
    """
    class MyRLEnv(Base5ActionRLEnv):
        """
        用户自定义环境。此类继承自 BaseEnvironment 和 gym.Env。
        用户可以重构这些父类的任何函数。以下是用户自定义 `calculate_reward()` 函数的示例。

        警告！
        此函数是一个功能的展示，旨在展示尽可能多的环境控制特性。
        它也被设计成可以在小型计算机上快速运行。这只是一个基准测试，*不* 用于实盘生产环境。
        """
        def calculate_reward(self, action: int) -> float:
            # 首先，如果动作无效则惩罚
            if not self._is_valid(action):
                return -2
            pnl = self.get_unrealized_profit()

            factor = 100

            pair = self.pair.replace(':', '')

            # 您可以使用来自 dataframe 的特征值
            # 假设策略中已生成了平移后的 RSI 指标。
            rsi_now = self.raw_features[f"%-rsi-period_10_shift-1_{pair}_"
                            f"{self.config['timeframe']}"].iloc[self._current_tick]

            # 奖励代理进场
            if (action in (Actions.Long_enter.value, Actions.Short_enter.value)
                    and self._position == Positions.Neutral):
                if rsi_now < 40:
                    factor = 40 / rsi_now
                else:
                    factor = 1
                return 25 * factor

            # 劝阻代理不要不进入交易
            if action == Actions.Neutral.value and self._position == Positions.Neutral:
                return -1
            max_trade_duration = self.rl_config.get('max_trade_duration_candles', 300)
            trade_duration = self._current_tick - self._last_trade_tick
            if trade_duration <= max_trade_duration:
                factor *= 1.5
            elif trade_duration > max_trade_duration:
                factor *= 0.5
            # 劝阻长时间持仓
            if self._position in (Positions.Short, Positions.Long) and \
            action == Actions.Neutral.value:
                return -1 * trade_duration / max_trade_duration
            # 平多
            if action == Actions.Long_exit.value and self._position == Positions.Long:
                if pnl > self.profit_aim * self.rr:
                    factor *= self.rl_config['model_reward_parameters'].get('win_reward_factor', 2)
                return float(pnl * factor)
            # 平空
            if action == Actions.Short_exit.value and self._position == Positions.Short:
                if pnl > self.profit_aim * self.rr:
                    factor *= self.rl_config['model_reward_parameters'].get('win_reward_factor', 2)
                return float(pnl * factor)
            return 0.
```

## 使用 Tensorboard

强化学习模型受益于跟踪训练指标。FreqAI 集成了 Tensorboard，允许用户跨所有币种、跨所有重新训练过程跟踪训练和评估表现。Tensorboard 通过以下命令激活：

```bash
tensorboard --logdir user_data/models/unique-id
```

其中 `unique-id` 是在 `freqai` 配置文件中设置的 `identifier`。此命令必须在单独的 shell 中运行，以便在浏览器中通过 127.0.0.1:6006 查看输出（6006 是 Tensorboard 使用的默认端口）。

![tensorboard](../assets/tensorboard.jpg)

## 自定义日志 (Custom logging)

FreqAI 还提供了一个内置的名为 `self.tensorboard_log` 的分集总结记录器 (episodic summary logger)，用于向 Tensorboard 日志添加自定义信息。默认情况下，该函数已在环境内部每步调用一次以记录代理动作。在单分集的所有步骤中累积的所有值都会在每个分集结束时上报，随后所有指标都会重置为 0，以为后续分集做准备。

`self.tensorboard_log` 也可以在环境内的任何地方使用，例如，可以将其添加到 `calculate_reward` 函数中，以收集关于奖励各个部分被调用频率的更详细信息：

```python
    class MyRLEnv(Base5ActionRLEnv):
        """
        用户自定义环境。此类继承自 BaseEnvironment 和 gym.Env。
        用户可以重构这些父类的任何函数。以下是用户自定义 `calculate_reward()` 函数的示例。
        """
        def calculate_reward(self, action: int) -> float:
            if not self._is_valid(action):
                self.tensorboard_log("invalid")
                return -2

```

!!! Note
    `self.tensorboard_log()` 函数旨在仅跟踪增量对象，例如训练环境中的事件、动作。如果感兴趣的事件是浮点数，则可以将该浮点数作为第二个参数传递，例如 `self.tensorboard_log("float_metric1", 0.23)`。在这种情况下，指标值不会递增。

## 选择基础环境

FreqAI 提供了三种基础环境：`Base3ActionRLEnvironment`、`Base4ActionEnvironment` 和 `Base5ActionEnvironment`。顾名思义，这些环境专门为可以从 3、4 或 5 个动作中进行选择的代理而定制。`Base3ActionEnvironment` 是最简单的，代理可以从观望 (hold)、做多 (long) 或做空 (short) 中进行选择。此环境也可用于仅做多机器人（它会自动遵循策略中的 `can_short` 标志），其中多头为进场条件，空头为离场条件。与此同时，在 `Base4ActionEnvironment` 中，代理可以做多进场、做空进场、保持中性状态或离场平仓。最后，在 `Base5ActionEnvironment` 中，代理拥有与 Base4 相同的动作，但它不再使用单一的平仓动作，而是分离了平多和平空动作。选择这些环境带来的主要变化包括：

* `calculate_reward` 中可用的动作
* 用户策略所消费的动作

所有 FreqAI 提供的环境都继承自一个名为 `BaseEnvironment` 的不依赖具体动作/持仓的环境对象，该对象包含所有共享逻辑。其架构设计旨在易于被定制。最简单的定制是 `calculate_reward()`（[详见此处](#创建自定义奖励函数)）。但是，定制可以进一步扩展到环境内的任何函数。您只需在预测模型文件中的 `MyRLEnv` 内部重写这些函数即可。或者对于更高级的定制，建议创建一个继承自 `BaseEnvironment` 的全新环境。

!!! Note
    只有 `Base3ActionRLEnv` 可以进行仅做多训练/交易（在用户策略属性中设置 `can_short = False`）。

---

原始文件来源: [docs/freqai-reinforcement-learning.md](docs/freqai-reinforcement-learning.md)
