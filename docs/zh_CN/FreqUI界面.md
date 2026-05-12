# FreqUI 界面

Freqtrade 提供了一个内置的 Web 服务器，它可以托管 [FreqUI](https://github.com/freqtrade/frequi)，即 Freqtrade 前端。

默认情况下，UI 会作为安装（脚本、Docker）的一部分自动安装。
也可以使用 `freqtrade install-ui` 命令手动安装 FreqUI。
相同的命令也可以用于将 FreqUI 更新到新版本。

一旦机器人在交易/模拟模式下启动（使用 `freqtrade trade`），UI 将在配置的 API 端口下可用（默认为 `http://127.0.0.1:8080`）。

??? Note "想要为 FreqUI 做出贡献？"
    开发者不应使用此方法，而应克隆相应的代码库，并使用 [FreqUI 代码库](https://github.com/freqtrade/frequi)中描述的方法来获取 FreqUI 的源代码。构建前端需要安装 node。

!!! tip "运行 Freqtrade 并不必须使用 FreqUI"
    FreqUI 是 Freqtrade 的可选组件，运行机器人并不必需。
    它是一个可以用来监控机器人并与其交互的前端——但 Freqtrade 本身在没有它的情况下也可以完美运行。

## 配置

FreqUI 没有自己的配置文件，而是假设已配置好 [REST API](REST-API.md)。
请参考相应的文档页面来设置 FreqUI。

## 界面

FreqUI 是一个现代、响应式的 Web 应用程序，可用于监控机器人并与其交互。

FreqUI 提供了浅色和深色主题。
可以通过页面顶部的显著按钮轻松切换主题。
本页截图的主题将适配所选的文档主题，因此要查看深色（或浅色）版本，请切换文档的主题。

### 登录

下面的截图显示了 FreqUI 的登录界面。

![FreqUI - 登录](../assets/frequi-login-CORS.png#only-dark)
![FreqUI - 登录](../assets/frequi-login-CORS-light.png#only-light)

!!! Hint "CORS"
    此截图中显示的 CORS 错误是由于 UI 在与 API 不同的端口上运行，并且尚未正确设置 [CORS](#cors)。

### 交易视图

交易视图允许您可视化机器人正在进行的交易并与其交互。
在此页面上，您还可以通过启动和停止机器人来与其交互，并且（如果已配置）可以强制执行入场和出场。

![FreqUI - 交易视图](../assets/freqUI-trade-pane-dark.png#only-dark)
![FreqUI - 交易视图](../assets/freqUI-trade-pane-light.png#only-light)

### 绘图配置器 (Plot Configurator)

FreqUI 图表可以通过策略中的 `plot_config` 配置对象（可以通过“来自策略”按钮加载）或通过 UI 进行配置。
可以创建多个绘图配置并随意切换——从而允许灵活地以不同视角查看您的图表。

绘图配置可以通过交易视图右上角的“绘图配置器”（齿轮图标）按钮访问。

![FreqUI - 绘图配置](../assets/freqUI-plot-configurator-dark.png#only-dark)
![FreqUI - 绘图配置](../assets/freqUI-plot-configurator-light.png#only-light)

### 设置

通过访问设置页面可以更改几个与 UI 相关的设置。

您可以更改的内容包括：

* UI 的时区
* 在 Favicon（浏览器标题栏图标）中可视化开放交易
* K 线颜色（涨/跌 -> 绿/红）
* 启用/禁用应用内通知类型

![FreqUI - 设置视图](../assets/frequi-settings-dark.png#only-dark)
![FreqUI - 设置视图](../assets/frequi-settings-light.png#only-light)

## Web 服务器模式

当 Freqtrade 以 [Web 服务器模式](实用工具.md#webserver-模式)启动（使用 `freqtrade webserver` 启动）时，Web 服务器将以特殊模式启动，允许使用其他功能，例如：

* 下载数据
* 测试交易对列表 (Pairlists)
* [回测策略](#回测)
* ...待扩展

### 回测

当 Freqtrade 以 [Web 服务器模式](实用工具.md#webserver-模式)启动（使用 `freqtrade webserver` 启动）时，回测视图将可用。
此视图允许您回测策略并可视化结果。

您还可以加载和可视化以前的回测结果，以及相互比较结果。

![FreqUI - 回测](../assets/freqUI-backtesting-dark.png#only-dark)
![FreqUI - 回测](../assets/freqUI-backtesting-light.png#only-light)

--8<-- "zh_CN/includes/cors.md"

---
原始文件来源: [docs/freq-ui.md](docs/freq-ui.md)
