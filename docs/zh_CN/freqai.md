![freqai-logo](../assets/freqai_doc_logo.svg)

# FreqAI

## 介绍

FreqAI 是一款旨在自动执行与训练预测性机器学习模型相关的各种任务的软件，以便在给定一组输入信号的情况下生成市场预测。总的来说，FreqAI 旨在成为一个轻松地在实时数据上部署强大的机器学习库的沙箱（[详情](#freqai-在开源机器学习领域中的地位)）。

!!! Note "注意"
    FreqAI 过去是，且永远是一个非营利性的开源项目。FreqAI *没有* 代币，FreqAI *不* 出售信号，并且 FreqAI 除了目前的 [freqtrade 文档](https://www.freqtrade.io/en/latest/freqai/) 之外没有其他域名。

功能包括：

* **自适应再训练 (Self-adaptive retraining)** - 在 [实时部署](freqai-running.md#实时部署) 期间重新训练模型，以有监督的方式自适应市场变化。
* **快速特征工程 (Rapid feature engineering)** - 基于简单的用户创建策略，创建大型丰富的 [特征集](freqai-feature-engineering.md#特征工程)（10k+ 特征）。
* **高性能 (High performance)** - 多线程允许在与模型推理（预测）和机器人交易操作分开的线程（或 GPU，如果可用）上进行自适应模型再训练。最新的模型和数据保存在 RAM 中以实现快速推理。
* **真实的回测 (Realistic backtesting)** - 通过自动重新训练的 [回测模块](freqai-running.md#回测)，在历史数据上模拟自适应训练。
* **可扩展性 (Extensibility)** - 泛用且健壮的架构允许整合 Python 中可用的任何 [机器学习库/方法](freqai-configuration.md#使用不同的预测模型)。目前提供八个示例，包括分类器、回归器和卷积神经网络。
* **智能离群值移除 (Smart outlier removal)** - 使用各种 [离群值检测技术](freqai-feature-engineering.md#离群值检测) 从训练和预测数据集中移除离群值。
* **崩溃弹性 (Crash resilience)** - 将训练好的模型存储到磁盘，以便在崩溃后快速轻松地重新加载，并 [清理过期文件](freqai-running.md#清理旧模型数据) 以支持持续的模拟/实盘运行。
* **自动数据归一化 (Automatic data normalization)** - 以一种智能且在统计上安全的方式 [归一化数据](freqai-feature-engineering.md#构建数据流水线)。
* **自动数据下载 (Automatic data download)** - 计算数据下载的时间范围，并更新历史数据（在实时部署中）。
* **输入数据清理 (Cleaning of incoming data)** - 在训练和模型推理之前安全地处理 NaN（空值）。
* **降维 (Dimensionality reduction)** - 通过 [主成分分析 (PCA)](freqai-feature-engineering.md#使用主成分分析进行数据降维) 减小训练数据的规模。
* **部署机器人机群 (Deploying bot fleets)** - 设置一个机器人训练模型，而一机群的 [消费者 (consumers)](producer-consumer.md) 使用这些信号。

## 快速上手 (Quick start)

快速测试 FreqAI 的最简单方法是使用以下命令在干跑（dry）模式下运行它：

```bash
freqtrade trade --config config_examples/config_freqai.example.json --strategy FreqaiExampleStrategy --freqaimodel LightGBMRegressor --strategy-path freqtrade/templates
```

您将看到自动数据下载的启动过程，随后是同步进行的训练和交易。

!!! danger "非生产环境使用"
    Freqtrade 源代码中提供的示例策略旨在展示/测试各种 FreqAI 功能。它还被设计为可以在小型计算机上运行，以便作为开发人员和用户之间的基准。该策略 *不* 适合在生产环境运行。

作为起点的示例策略、预测模型和配置分别可以在 `freqtrade/templates/FreqaiExampleStrategy.py`、`freqtrade/freqai/prediction_models/LightGBMRegressor.py` 和 `config_examples/config_freqai.example.json` 中找到。

## 通用方案 (General approach)

您向 FreqAI 提供一组自定义 *基础指标*（方式与 [典型的 Freqtrade 策略](策略自定义.md) 相同）以及目标值（*标签 (labels)*）。对于白名单中的每个交易对，FreqAI 会根据自定义指标的输入训练一个模型来预测目标值。然后，模型会按照预定的频率持续重新训练，以适应市场状况。FreqAI 提供了对策略进行回测（通过对历史数据进行定期重新训练来模拟现实）和部署模拟/实盘运行的能力。在模拟/实盘条件下，FreqAI 可以设置为在后台线程中不断重新训练，以保持模型尽可能最新。

下面展示了算法概述，解释了数据处理流水线和模型使用情况。

![freqai-algo](../assets/freqai_algo.jpg)

### 重要的机器学习术语

**特征 (Features)** - 基于历史数据的参数，模型据此进行训练。单根 K 线的所有特征都存储为一个向量。在 FreqAI 中，您可以利用在策略中可以构建的任何内容来构建特征数据集。

**标签 (Labels)** - 模型训练的目标值。每个特征向量都与您在策略中定义的一个标签相关联。这些标签是有意看向未来的，它们正是您训练模型能够预测的内容。

**训练 (Training)** - “教”模型将特征集与相关标签匹配的过程。不同类型的模型以不同的方式“学习”，这意味着一个模型在特定应用中可能优于另一个。有关 FreqAI 中已实现的不同模型的更多信息，可以在 [此处](freqai-configuration.md#使用不同的预测模型) 找到。

**训练数据 (Train data)** - 特征数据集的一个子集，在训练期间馈送给模型，以“教”模型如何预测目标。这些数据直接影响模型中的权重连接。

**测试数据 (Test data)** - 特征数据集的一个子集，用于在训练后评估模型的性能。这些数据不影响模型内的节点权重。

**推理 (Inferencing)** - 将新的、未见过的数据输入到训练好的模型中，由模型作出预测的过程。

## 安装先决条件 (Install prerequisites)

正常的 Freqtrade 安装过程会询问您是否希望安装 FreqAI 依赖项。如果您希望使用 FreqAI，应对此问题回答“yes”。如果您最初没有选择安装，可以在安装后通过以下方式手动安装这些依赖项：

``` bash
pip install -r requirements-freqai.txt
```

!!! Note "注意"
    Catboost 不会自动安装在低功耗 ARM 设备（如树莓派）上，因为它不为该平台提供 Wheels。

### 在 Docker 中使用

如果您使用 Docker，可以使用带有 FreqAI 依赖项的特定标签 `:freqai`。因此，您可以将 Docker Compose 文件中的映像行替换为 `image: freqtradeorg/freqtrade:stable_freqai`。此映像包含常规的 FreqAI 依赖项。与原生安装类似，Catboost 在基于 ARM 的设备上不可用。如果您想使用 PyTorch 或强化学习，应使用 torch 或 RL 标签，例如 `image: freqtradeorg/freqtrade:stable_freqaitorch`, `image: freqtradeorg/freqtrade:stable_freqairl`。

!!! note "docker-compose-freqai.yml"
    我们在 `docker/docker-compose-freqai.yml` 中提供了明确的 Docker Compose 文件 —— 既可以通过 `docker compose -f docker/docker-compose-freqai.yml run ...` 使用，也可以复制并替换原始 Docker 文件。该 Docker Compose 文件还包含一个（禁用的）部分，用于在 Docker 容器中启用 GPU 资源。这显然假设系统本身有可用的 GPU 资源。

### FreqAI 在开源机器学习领域中的地位

预测基于混乱时间序列的系统（如股票/加密货币市场）需要一套广泛的工具来测试各种假设。幸运的是，近期强大的机器学习库（如 `scikit-learn`）的成熟开辟了大量的研究可能性。来自各个领域的科学家现在可以轻松地在大量成熟的机器学习算法上原型化他们的研究。同样，这些用户友好的库也使“民间科学家”能够利用他们的基本 Python 技能进行数据探索。然而，在历史和实时混乱数据源上利用这些机器学习库，在逻辑上可能非常困难且成本高昂。此外，稳健的数据收集、存储和处理也呈现出由于不同应用场景而产生的挑战。[`FreqAI`](#freqai) 旨在提供一个通用的、可扩展的开源框架，面向市场预测的自适应建模的实时部署。`FreqAI` 框架实际上是丰富多彩的开源机器学习库世界的沙箱。在 `FreqAI` 沙箱中，用户发现他们可以结合各种第三方库，在开源 24/7 混乱数据源（加密货币交易所数据）上测试富有创意的假设。

### 引用 FreqAI

FreqAI 已 [发表于开源软件期刊 (Journal of Open Source Software)](https://joss.theoj.org/papers/10.21105/joss.04864)。如果您发现 FreqAI 在您的研究中很有用，请使用以下引用：

```bibtex
@article{Caulk2022, 
    doi = {10.21105/joss.04864},
    url = {https://doi.org/10.21105/joss.04864},
    year = {2022}, publisher = {The Open Journal},
    volume = {7}, number = {80}, pages = {4864},
    author = {Robert A. Caulk and Elin Törnquist and Matthias Voppichler and Andrew R. Lawless and Ryan McMullan and Wagner Costa Santos and Timothy C. Pogue and Johan van der Vlugt and Stefan P. Gehring and Pascal Schmidt},
    title = {FreqAI: generalizing adaptive modeling for chaotic time-series market forecasts},
    journal = {Journal of Open Source Software} } 
```

## 常见陷阱 (Common pitfalls)

FreqAI 不能与动态的 `VolumePairlists`（或任何动态增加或删除交易对的交易对列表过滤器）结合使用。
这是出于性能原因 —— FreqAI 依赖于进行快速的预测/再训练。为了有效地做到这一点，它需要在模拟/实盘实例开始时下载所有的训练数据。FreqAI 会自动存储并附加新的 K 线，以供未来的再训练使用。这意味着，如果在模拟运行期间由于成交量交易对列表而后来加入了新的交易对，它将没有准备好数据。不过，FreqAI 确实可以与 `ShufflePairlist` 或保持总交易对列表恒定（但根据成交量重新排序）的 `VolumePairlist` 配合使用。

## 附加学习材料

这里我们收集了一些外部材料，可以更深入地了解 FreqAI 的各个组件：

- [实时对决：使用 XGBoost 和 CatBoost 对金融市场数据进行自适应建模](https://emergentmethods.medium.com/real-time-head-to-head-adaptive-modeling-of-financial-market-data-using-xgboost-and-catboost-995a115a7495)
- [FreqAI - 从价格到预测](https://emergentmethods.medium.com/freqai-from-price-to-prediction-6fadac18b665)


## 支持 (Support)

您可以在许多地方找到对 FreqAI 的支持，包括 [Freqtrade Discord](https://discord.gg/Jd8JYeWHc4)、专门的 [FreqAI Discord](https://discord.gg/7AMWACmbjT) 以及 [GitHub Issues](https://github.com/freqtrade/freqtrade/issues)。

## 致谢 (Credits)

FreqAI 由一群个人开发，他们都为该项目贡献了特定的技能。

概念与软件开发：
Robert Caulk @robcaulk

理论推演与数据分析：
Elin Törnquist @th0rntwig

代码审查与软件架构脑暴：
@xmatthias

软件开发：
Wagner Costa @wagnercosta
Emre Suzen @aemr3
Timothy Pogue @wizrds

Beta 测试与错误报告：
Stefan Gehring @bloodhunter4rc, @longyu, Andrew Lawless @paranoidandy, Pascal Schmidt @smidelis, Ryan McMullan @smarmau, Juha Nykänen @suikula, Johan van der Vlugt @jooopiert, Richárd Józsa @richardjosza

---

原始文件来源: [docs/freqai.md](docs/freqai.md)
