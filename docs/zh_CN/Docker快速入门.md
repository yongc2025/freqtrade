# 在 Docker 中使用 Freqtrade

本页介绍了如何使用 Docker 运行机器人。这并不意味着它可以开箱即用。您仍需要阅读完整文档并了解如何正确配置它。

## 安装 Docker

首先为您的平台下载并安装 Docker / Docker Desktop：

* [Mac](https://docs.docker.com/docker-for-mac/install/)
* [Windows](https://docs.docker.com/docker-for-windows/install/)
* [Linux](https://docs.docker.com/install/)

!!! Info "Docker Compose 安装"
    Freqtrade 文档假设使用 Docker Desktop（或 Docker Compose 插件）。
    虽然独立的 docker-compose 安装仍然有效，但它需要将所有的 `docker compose` 命令从 `docker compose` 更改为 `docker-compose` 才能工作（例如，`docker compose up -d` 将变为 `docker-compose up -d`）。

??? Warning "Windows 上的 Docker"
    如果您刚在 Windows 系统上安装了 Docker，请务必重启系统，否则您可能会遇到与 Docker 容器网络连接相关的无法解释的问题。

## Docker 版本的 Freqtrade

Freqtrade 在 [Dockerhub](https://hub.docker.com/r/freqtradeorg/freqtrade/) 上提供官方 Docker 镜像，同时也提供了一个准备好的 [docker-compose 文件](https://github.com/freqtrade/freqtrade/blob/stable/docker-compose.yml)。

!!! Note "注意"
    - 以下部分假设 `docker` 已安装且对当前登录用户可用。
    - 下面的所有命令都使用相对目录，且必须从包含 `docker-compose.yml` 文件的目录中执行。

### Docker 快速入门

创建一个新目录并将 [docker-compose 文件](https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml) 放入该目录中。

``` bash
mkdir ft_userdata
cd ft_userdata/
# 从仓库下载 docker-compose 文件
curl https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml -o docker-compose.yml

# 拉取 freqtrade 镜像
docker compose pull

# 创建用户目录结构
docker compose run --rm freqtrade create-userdir --userdir user_data

# 创建配置 - 需要回答交互式问题
docker compose run --rm freqtrade new-config --config user_data/config.json
```

上述代码片段创建了一个名为 `ft_userdata` 的新目录，下载了最新的 compose 文件并拉取了 freqtrade 镜像。
最后两步创建了带有 `user_data` 的目录，并根据您的选择（交互式地）创建了默认配置。

!!! Question "如何编辑机器人配置？"
    配置随时可以编辑。使用上述配置时，可以在 `user_data/config.json`（位于 `ft_userdata` 目录下）找到配置文件。

    您还可以通过编辑 `docker-compose.yml` 文件的 command 部分来更改策略和命令。

#### 添加自定义策略

1. 配置文件现在位于 `user_data/config.json`。
2. 将自定义策略复制到 `user_data/strategies/` 目录中。
3. 将策略的类名添加到 `docker-compose.yml` 文件中。

默认运行的是 `SampleStrategy`。

!!! Danger "`SampleStrategy` 仅供演示！"
    `SampleStrategy` 仅供您参考并为您提供自己的策略思路。
    在拿真钱冒险之前，请始终回测您的策略并进行一段时间的干跑（Dry-run）！
    您可以在 [策略文档](strategy-customization.md) 中找到关于策略开发的更多信息。

完成后，您就可以在交易模式下启动机器人了（取决于您之前对相应问题的回答，可以是干跑模式或实盘交易模式）。

``` bash
docker compose up -d
```

!!! Warning "默认配置"
    虽然生成的配置大部分功能正常，但在启动机器人之前，您仍需要验证所有选项（如定价、交易对列表等）是否符合您的要求。

#### 访问 UI

如果您在 `new-config` 步骤中选择了启用 FreqUI，那么您可以通过端口 `localhost:8080` 访问 FreqUI。

现在可以通过在浏览器中输入 `localhost:8080` 来访问 UI。

??? Note "在远程服务器上访问 UI"
    如果您在 VPS 上运行，您应该考虑使用 SSH 隧道或设置 VPN (OpenVPN, WireGuard) 来连接您的机器人。
    这将确保 FreqUI 不会直接暴露在互联网上，出于安全原因，不建议直接暴露（FreqUI 本身不支持 HTTPS）。
    这些工具的安装不属于本教程的一部分，但互联网上可以找到很多优秀的教程。
    另请阅读 [API 配置与 Docker](rest-api.md#configuration-with-docker) 部分以了解有关此配置的更多信息。

#### 监控机器人

您可以使用 `docker compose ps` 检查正在运行的实例。
这应该会将 `freqtrade` 服务列为 `running`。如果不是这种情况，最好检查日志（见下一点）。

#### Docker Compose 日志

日志将写入：`user_data/logs/freqtrade.log`。
您也可以使用命令 `docker compose logs -f` 查看最新日志。

#### 数据库

数据库将位于：`user_data/tradesv3.sqlite`

#### 使用 Docker 更新 Freqtrade

使用 `docker` 时更新 Freqtrade 非常简单，只需运行以下两条命令：

``` bash
# 下载最新镜像
docker compose pull
# 重启镜像
docker compose up -d
```

这将首先拉取最新镜像，然后使用刚刚拉取的版本重启容器。

!!! Warning "检查更改日志 (Changelog)"
    您应该始终检查更改日志，了解是否有破坏性更改或需要手动干预的操作，并确保更新后机器人能正常启动。

### 编辑 docker-compose 文件

高级用户可以进一步编辑 docker-compose 文件，以包含所有可能的选项或参数。

所有 freqtrade 参数都可以通过运行 `docker compose run --rm freqtrade <command> <optional arguments>` 来调用。

!!! Warning "针对交易命令使用 `docker compose`"
    交易命令 (`freqtrade trade <...>`) 不应通过 `docker compose run` 运行，而应使用 `docker compose up -d` 代替。
    这确保了容器被正确启动（包括端口转发），并确保容器在系统重启后会自动重启。
    如果您打算使用 FreqUI，请务必[相应地调整配置](rest-api.md#configuration-with-docker)，否则 UI 将无法使用。

!!! Note "`docker compose run --rm`"
    包含 `--rm` 选项将在完成后删除容器，除了交易模式（使用 `freqtrade trade` 命令运行）外，强烈建议在所有模式下使用此选项。

??? Note "不使用 Docker Compose 而直接使用 Docker"
    "`docker compose run --rm`" 需要提供 compose 文件。
    某些不需要身份验证的 freqtrade 命令（如 `list-pairs`）可以使用 "`docker run --rm`" 代替。
    例如 `docker run --rm freqtradeorg/freqtrade:stable list-pairs --exchange binance --quote BTC --print-json`。
    这对于获取交易所信息并添加到 `config.json` 中非常有用，且不会影响正在运行的容器。

#### 示例：使用 Docker 下载数据

下载 Binance 交易所 ETH/BTC 交易对、1 小时时间范围、为期 5 天的回测数据。数据将存储在主机的 `user_data/data/` 目录中。

``` bash
docker compose run --rm freqtrade download-data --pairs ETH/BTC --exchange binance --days 5 -t 1h
```

有关下载数据的更多细节，请查看[数据下载文档](data-download.md)。

#### 示例：使用 Docker 运行回测

在 Docker 容器中为 SampleStrategy 运行回测，针对指定时间范围的历史数据，使用 5 分钟时间范围：

``` bash
docker compose run --rm freqtrade backtesting --config user_data/config.json --strategy SampleStrategy --timerange 20190801-20191001 -i 5m
```

了解更多信息，请查阅[回测文档](backtesting.md)。

### Docker 的额外依赖

如果您的策略需要默认镜像中未包含的依赖项，则需要在您的主机上构建镜像。
为此，请创建一个包含额外依赖项安装步骤的 Dockerfile（可以参考 [docker/Dockerfile.custom](https://github.com/freqtrade/freqtrade/blob/develop/docker/Dockerfile.custom)）。

然后，您还需要修改 `docker-compose.yml` 文件，取消 build 步骤的注释，并重命名镜像以避免命名冲突。

``` yaml
    image: freqtrade_custom
    build:
      context: .
      dockerfile: "./Dockerfile.<yourextension>"
```

之后，您可以运行 `docker compose build --pull` 来构建 Docker 镜像，并使用上述命令运行它。

### 使用 Docker 绘图

可以通过在 `docker-compose.yml` 文件中将镜像更改为 `*_plot` 来使用 `freqtrade plot-profit` 和 `freqtrade plot-dataframe` 命令（[文档](plotting.md)）。
然后，您可以按如下方式使用这些命令：

``` bash
docker compose run --rm freqtrade plot-dataframe --strategy AwesomeStrategy -p BTC/ETH --timerange=20180801-20180805
```

输出将存储在 `user_data/plot` 目录中，可以使用任何现代浏览器打开。

### 使用 Docker Compose 进行数据分析

Freqtrade 提供了一个 docker-compose 文件，可以启动 Jupyter Lab 服务器。
您可以使用以下命令运行此服务器：

``` bash
docker compose -f docker/docker-compose-jupyter.yml up
```

这将创建一个运行 Jupyter Lab 的 Docker 容器，可以通过 `https://127.0.0.1:8888/lab` 访问。
启动后请使用控制台中打印的链接进行简化登录。

由于此镜像的一部分是在您的机器上构建的，建议不时重新构建镜像以保持 freqtrade（及其依赖项）处于最新状态。

``` bash
docker compose -f docker/docker-compose-jupyter.yml build --no-cache
```

## 故障排除

### Windows 上的 Docker

* 错误：`"Timestamp for this request is outside of the recvWindow."`
  市场 API 请求需要同步时钟，但 Docker 容器内的时间会随着时间推移出现滞后。
  临时解决方法是运行 `wsl --shutdown` 并重新启动 Docker（Windows 10 上会弹出窗口要求您这样做）。
  永久解决方法是将 Docker 容器托管在 Linux 主机上，或通过任务计划程序不时重启 WSL。

  ``` bash
  taskkill /IM "Docker Desktop.exe" /F
  wsl --shutdown
  start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  ```

* 无法连接到 API (Windows)
  如果您在 Windows 上并刚安装了 Docker (Desktop)，请务必重启系统。Docker 在不重启的情况下可能会出现网络连接问题。
  您显然还应该确保您的[设置](#访问-ui)正确。

!!! Warning "警告"
    鉴于上述原因，我们不建议在 Windows 生产环境中使用 Docker，它仅适用于实验、数据下载和回测。
    运行可靠的 Freqtrade 实例，最好使用 Linux VPS。

---

原始文件来源: [docs/docker_quickstart.md](docs/docker_quickstart.md)
