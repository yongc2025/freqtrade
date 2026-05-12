# REST API 接口 (REST API)

## FreqUI

FreqUI 现在有了专门的 [文档章节](FreqUI界面.md) —— 请参阅该章节获取有关 FreqUI 的所有信息。

## 配置

通过在配置中添加 `api_server` 部分并将 `api_server.enabled` 设置为 `true` 来启用 REST API。

配置示例：

``` json
    "api_server": {
        "enabled": true,
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "verbosity": "error",
        "enable_openapi": false,
        "jwt_secret_key": "somethingrandom",
        "CORS_origins": [],
        "username": "Freqtrader",
        "password": "SuperSecret1!",
        "ws_token": "sercet_Ws_t0ken"
    },
```

!!! Danger "安全警告"
    默认情况下，配置仅监听 localhost（因此无法从其他系统访问）。我们强烈建议不要将此 API 暴露给互联网，并选择一个强且唯一的密码，因为其他人可能会控制您的机器人。

??? Note "远程服务器上的 API/UI 访问"
    如果您在 VPS 上运行，您应该考虑使用 SSH 隧道或设置 VPN（OpenVPN, Wireguard）来连接到您的机器人。
    这将确保 FreqUI 不会直接暴露给互联网，出于安全原因，不建议直接公开（FreqUI 不开箱即用地支持 HTTPS）。
    这些工具的安装不属于本教程的一部分，但在互联网上可以找到许多优秀的教程。

然后，您可以通过在浏览器中访问 `http://127.0.0.1:8080/api/v1/ping` 来检查 API 是否正常运行。
这应该返回响应：

``` output
{"status":"pong"}
```

所有其他端点都返回敏感信息且需要身份验证，因此无法通过网络浏览器直接访问。

### 安全

要生成安全的密码，最好使用密码管理器或使用以下代码。

``` python
import secrets
secrets.token_hex()
```

!!! Hint "JWT 令牌"
    使用相同的方法生成 JWT 密钥 (`jwt_secret_key`)。

!!! Danger "密码选择"
    请务必选择一个非常强且唯一的密码，以保护您的机器人免受未经授权的访问。
    同时将 `jwt_secret_key` 更改为随机字符串（不需要记住它，但它将被用于加密您的会话，所以最好是唯一的！）。

### Docker 中的配置

如果您使用 Docker 运行机器人，您需要让机器人监听传入的连接。安全性随后由 Docker 处理。

``` json
    "api_server": {
        "enabled": true,
        "listen_ip_address": "0.0.0.0",
        "listen_port": 8080,
        "username": "Freqtrader",
        "password": "SuperSecret1!",
        //...
    },
```

确保您的 `docker-compose` 文件中包含以下两行：

```yml
    ports:
      - "127.0.0.1:8080:8080"
```

!!! Danger "安全警告"
    通过在 Docker 端口映射中使用 `"8080:8080"` (或 `"0.0.0.0:8080:8080"`)，连接到该服务器并使用正确端口的每个人都可以访问该 API，因此其他人可能会控制您的机器人。
    如果您在安全的环境（如家庭网络）中运行机器人，这 **可能** 是安全的，但不建议将 API 暴露给互联网。

## Rest API

### 使用 API

我们建议使用受支持的 `freqtrade-client` 包（也可以作为 `scripts/rest_client.py` 获得）来使用 API。

可以通过使用 `pip install freqtrade-client` 独立于任何运行中的 freqtrade 机器人来安装此命令。

该模块设计轻量，仅依赖于 `requests` 和 `python-rapidjson` 模块，跳过了 freqtrade 原本需要的所有重型依赖。

``` bash
freqtrade-client <command> [optional parameters]
```

默认情况下，脚本假设使用 `127.0.0.1` (localhost) 和端口 `8080`，但您可以指定配置文件来覆盖此行为。

#### 简约客户端配置

``` json
{
    "api_server": {
        "enabled": true,
        "listen_ip_address": "0.0.0.0",
        "listen_port": 8080,
        "username": "Freqtrader",
        "password": "SuperSecret1!",
        //...
    }
}
```

``` bash
freqtrade-client --config rest_config.json <command> [optional parameters]
```

具有许多参数的命令可能需要关键字参数（为了清晰起见）—— 可以按照以下方式提供：

``` bash
freqtrade-client --config rest_config.json forceenter BTC/USDT long enter_tag=GutFeeling
```

该方法适用于所有参数 —— 查看 `show` 命令以获取可用参数列表。

??? Note "编程使用"
    `freqtrade-client` 包（可以独立于 freqtrade 安装）可以在您自己的脚本中使用，以便与 freqtrade API 交互。
    为此，请使用以下代码：

    ``` python
    from freqtrade_client import FtRestClient
    

    client = FtRestClient(server_url, username, password)

    # 获取机器人的状态
    ping = client.ping()
    print(ping)

    # 将交易对加入黑名单
    client.blacklist("BTC/USDT", "ETH/USDT")
    # 通过提供列表将交易对加入黑名单
    client.blacklist(*listPairs)
    # ... 
    ```

    有关可用命令的完整列表，请参阅下表。

#### Freqtrade 客户端 - 可用命令

可以使用 `help` 命令从 rest-client 脚本列出可能的命令。

``` bash
freqtrade-client help
```

--8<-- "zh_CN/includes/freqtrade-client.md"

### 可用端点 (Available endpoints)

如果您希望通过其他方式手动调用 REST API，例如直接通过 `curl`，下表显示了相关的 URL 端点和参数。
下表中的所有端点都需要以 API 的基础 URL 为前缀，例如 `http://127.0.0.1:8080/api/v1/` —— 因此命令变为 `http://127.0.0.1:8080/api/v1/<command>`。

| 端点 | 方法 | 描述 / 参数 |
|-----------|--------|--------------------------|
| `/ping` | GET | 测试 API 就绪情况的简单命令 —— 不需要身份验证。 |
| `/start` | POST | 启动交易机器人。 |
| `/pause` | POST | 暂停交易机器人。按照规则从容处理开仓交易。不进入新头寸。 |
| `/stop` | POST | 停止交易机器人。 |
| `/stopbuy` | POST | 停止机器人开新仓。按照规则从容关闭开仓交易。 |
| `/reload_config` | POST | 重新加载配置文件。 |
| `/trades` | GET | 列出最后的交易。每次调用限制为 500 个交易。 |
| `/trade/<tradeid>` | GET | 获取特定交易。<br/>*参数:*<br/>- `tradeid` (`int`) |
| `/trades/<tradeid>` | DELETE | 从数据库中删除交易。尝试关闭挂单。需要手动在交易所处理此交易。<br/>*参数:*<br/>- `tradeid` (`int`) |
| `/trades/<tradeid>/open-order` | DELETE | 取消此交易的挂单。<br/>*参数:*<br/>- `tradeid` (`int`) |
| `/trades/<tradeid>/reload` | POST | 从交易所重新加载交易。仅在实盘中有效，可能有助于恢复在交易所手动卖出的交易。<br/>*参数:*<br/>- `tradeid` (`int`) |
| `/show_config` | GET | 显示当前配置的一部分以及与运行相关的设置。 |
| `/logs` | GET | 显示最后的日志消息。 |
| `/status` | GET | 列出所有开仓交易。 |
| `/count` | GET | 显示已使用和可用的交易数量。 |
| `/entries` | GET | 显示给定对（或所有对，如果没有给出对）的每个入场标签的利润统计数据。交易对是可选的。<br/>*参数:*<br/>- `pair` (`str`) |
| `/exits` | GET | 显示给定对（或所有对，如果没有给出对）的每个退出原因的利润统计数据。交易对是可选的。<br/>*参数:*<br/>- `pair` (`str`) |
| `/mix_tags` | GET | 显示给定对（或所有对，如果没有给出对）的每个入场标签 + 退出原因组合的利润统计数据。交易对是可选的。<br/>*参数:*<br/>- `pair` (`str`) |
| `/locks` | GET | 显示当前锁定的交易对。 |
| `/locks` | POST | 锁定一个交易对直到 "until"。 (Until 将被向上舍入到最近的时间框架)。方向是可选的，可以是 `long` 或 `short`（默认是 `long`）。理由是可选的。<br/>*参数:*<br/>- `<pair>` (`str`)<br/>- `<until>` (`datetime`)<br/>- `[side]` (`str`)<br/>- `[reason]` (`str`) |
| `/locks/<lockid>` | DELETE | 通过 ID 删除（禁用）锁定。<br/>*参数:*<br/>- `lockid` (`int`) |
| `/profit` | GET | 显示已平仓交易的盈亏摘要以及有关您表现的一些统计数据。 |
| `/forceexit` | POST | 立即退出给定的交易（忽略 `minimum_roi`），使用给定的订单类型（"market" 或 "limit"，如果没有指定，则使用您的配置设置），以及选择的数量（如果未指定则全额卖出）。如果将 `all` 作为 `tradeid` 提供，则所有当前处于开启状态的交易都将被强制退出。<br/>*参数:*<br/>- `<tradeid>` (`int` 或 `str`)<br/>- `<ordertype>` (`str`)<br/>- `[amount]` (`float`) |
| `/forceenter` | POST | 立即进入给定的交易对。方向是可选的，可以是 `long` 或 `short`（默认是 `long`）。价格、投入金额、入场标签和杠杆是可选的。订单类型是可选的，可以是 `market` 或 `long`（默认使用配置中设置的值）。（`force_entry_enable` 必须设置为 True）<br/>*参数:*<br/>- `<pair>` (`str`)<br/>- `<side>` (`str`)<br/>- `[price]` (`float`)<br/>- `[ordertype]` (`str`)<br/>- `[stakeamount]` (`float`)<br/>- `[entry_tag]` (`str`)<br/>- `[leverage]` (`float`) |
| `/performance` | GET | 显示按对分组的每个已完成交易的表现。 |
| `/balance` | GET | 显示每个账户的货币余额。 |
| `/daily` | GET | 显示过去 n 天每天的利润或亏损（n 默认为 7）。<br/>*参数:*<br/>- `timescale` (`int`) |
| `/weekly` | GET | 显示过去 n 天每周的利润或亏损（n 默认为 4）。<br/>*参数:*<br/>- `timescale` (`int`) |
| `/monthly` | GET | 显示过去 n 天每月的利润或亏损（n 默认为 3）。<br/>*参数:*<br/>- `timescale` (`int`) |
| `/stats` | GET | 显示盈亏原因摘要以及平均持有时间。 |
| `/whitelist` | GET | 显示当前白名单。 |
| `/blacklist` | GET | 显示当前黑名单。 |
| `/blacklist` | POST | 将指定的对添加到黑名单。<br/>*参数:*<br/>- `blacklist` (`str`) |
| `/blacklist` | DELETE | 从黑名单中删除指定的对列表。<br/>*参数:*<br/>- `[pair,pair]` (`list[str]`) |
| `/pair_candles` | GET | 机器人运行时返回一对 / 时间范围组合的数据框。 **Alpha** |
| `/pair_candles` | POST | 机器人运行时返回一对 / 时间范围组合的数据框，通过提供的返回列列表进行过滤。 **Alpha**<br/>*参数:*<br/>- `<column_list>` (`list[str]`) |
| `/pair_history` | GET | 返回给定时间范围内的分析数据框，由给定策略分析。 **Alpha** |
| `/pair_history` | POST | 返回给定时间范围内的分析数据框，由给定策略分析，通过提供的返回列列表进行过滤。 **Alpha**<br/>*参数:*<br/>- `<column_list>` (`list[str]`) |
| `/plot_config` | GET | 从策略获取绘图配置（如果未配置则获取空）。 **Alpha** |
| `/strategies` | GET | 列出策略目录中的策略。 **Alpha** |
| `/strategy/<strategy>` | GET | 通过策略类名获取特定策略内容。 **Alpha**<br/>*参数:*<br/>- `<strategy>` (`str`) |
| `/available_pairs` | GET | 列出可用的回测数据。 **Alpha** |
| `/version` | GET | 显示版本。 |
| `/sysinfo` | GET | 显示有关系统负载的信息。 |
| `/health` | GET | 显示机器人健康状况（最后一个机器人循环）。 |

!!! Warning "Alpha status (Alpha 阶段)"
    标注有 *Alpha status* 的端点可能会在不通知的情况下随时更改。

### 消息 WebSocket

API 服务器包括一个 WebSocket 端点，用于订阅来自 freqtrade 机器人的 RPC 消息。
这可以用来从您的机器人消费实时数据，如开仓/平仓成交消息、白名单更改、填充了指标的交易对数据等等。

这也用于在 Freqtrade 中设置 [生产/消费模式 (Producer/Consumer mode)](producer-consumer.md)。

假设您的 REST API 设置为 `127.0.0.1` 端口 `8080`，则端点可在 `http://localhost:8080/api/v1/message/ws` 访问。

要访问 WebSocket 端点，需要将 `ws_token` 作为端点 URL 中的查询参数。

要生成安全的 `ws_token`，您可以运行以下代码：

``` python
>>> import secrets
>>> secrets.token_urlsafe(25)
'hZ-y58LXyX_HZ8O1cJzVyN6ePWrLpNQv4Q'
```

然后，您将在 `api_server` 配置下的 `ws_token` 项中添加该令牌。如下所示：

``` json
"api_server": {
    "enabled": true,
    "listen_ip_address": "127.0.0.1",
    "listen_port": 8080,
    "verbosity": "error",
    "enable_openapi": false,
    "jwt_secret_key": "somethingrandom",
    "CORS_origins": [],
    "username": "Freqtrader",
    "password": "SuperSecret1!",
    "ws_token": "hZ-y58LXyX_HZ8O1cJzVyN6ePWrLpNQv4Q" // <-----
},
```

现在，您可以连接到 `http://localhost:8080/api/v1/message/ws?token=hZ-y58LXyX_HZ8O1cJzVyN6ePWrLpNQv4Q`。

!!! Danger "重新使用示例令牌"
    请不要使用上述示例令牌。为了确保您的安全，请生成一个全新的令牌。

#### 使用 WebSocket

由于连接到 WebSocket，机器人将向订阅它们的任何人广播 RPC 消息。要订阅消息列表，必须通过 WebSocket 发送类似下面的 JSON 请求。`data` 键必须是消息类型字符串列表。

``` json
{
  "type": "subscribe",
  "data": ["whitelist", "analyzed_df"] // 字符串消息类型列表
}
```

有关消息类型列表，请参阅 `freqtrade/enums/rpcmessagetype.py` 中的 `RPCMessageType` 枚举。

现在，只要这些类型的 RPC 消息在机器人中发送，只要连接处于活动状态，您就会通过 WebSocket 接收它们。它们通常采取与请求相同的形式：

``` json
{
  "type": "analyzed_df",
  "data": {
      "key": ["NEO/BTC", "5m", "spot"],
      "df": {}, // 数据框
      "la": "2022-09-08 22:14:41.457786+00:00"
  }
}
```

#### 反向代理设置 (Reverse Proxy)

使用 [Nginx](https://nginx.org/en/docs/) 时，需要以下配置才能使 WebSocket 正常工作（注意此配置不完整，缺少一些信息，不能原样使用）：

请确保将 `<freqtrade_listen_ip>` (以及随后的端口) 替换为与您的配置/设置匹配的 IP 和端口。

```
http {
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    #...

    server {
        #...

        location / {
            proxy_http_version 1.1;
            proxy_pass http://<freqtrade_listen_ip>:8080;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
        }
    }
}
```

要正确配置（安全地）反向代理，请查阅其有关代理 WebSocket 的文档。

- **Traefik**: Traefik 开箱即用地支持 WebSocket，请参阅 [文档](https://doc.traefik.io/traefik/)
- **Caddy**: Caddy v2 开箱即用地支持 WebSocket，请参阅 [文档](https://caddyserver.com/docs/v2-upgrade#proxy)

!!! Tip "SSL 证书"
    您可以使用 certbot 等工具设置 SSL 证书，通过上述任何反向代理使用加密连接访问机器人的 UI。
    虽然这会保护传输中的数据，但我们不建议在私有网络 (VPN, SSH 隧道) 之外运行 freqtrade API。

### OpenAPI 界面

要启用内置的 OpenAPI 界面（Swagger UI），请在 api_server 配置中指定 `"enable_openapi": true`。
这将在 `/docs` 端点启用 Swagger UI。默认情况下，它运行在 <http://localhost:8080/docs> —— 但这取决于您的设置。

### 使用 JWT 令牌的高级 API 用法

!!! Note "注意"
    以下操作应在应用程序（一个通过 API 获取信息的 Freqtrade REST API 客户端）中完成，不打算日常手动使用。

Freqtrade 的 REST API 还提供 JWT (JSON Web Tokens)。
您可以使用以下命令登录，并随后使用生成的 `access_token`。

``` bash
> curl -X POST --user Freqtrader http://localhost:8080/api/v1/token/login
{"access_token":"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE1ODkxMTk2ODEsIm5iZiI6MTU4OTExOTY4MSwianRpIjoiMmEwYmY0NWUtMjhmOS00YTUzLTlmNzItMmM5ZWVlYThkNzc2IiwiZXhwIjoxNTg5MTIwNTgxLCJpZGVudGl0eSI6eyJ1IjoiRnJlcXRyYWRlciJ9LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.qt6MAXYIa-l556OM7arBvYJ0SDI9J8bIk3_glDujF5g","refresh_token":"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE1ODkxMTk2ODEsIm5iZiI6MTU4OTExOTY4MSwianRpIjoiZWQ1ZWI3YjAtYjMwMy00YzAyLTg2N2MtNWViMjIxNWQ2YTMxIiwiZXhwIjoxNTkxNzExNjgxLCJpZGVudGl0eSI6eyJ1IjoiRnJlcXRyYWRlciJ9LCJ0eXBlIjoicmVmcmVzaCJ9.d1AT_jYICyTAjD0fiQAr52rkRqtxCjUGEMwlNuuzgNQ"}

> access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE1ODkxMTk2ODEsIm5iZiI6MTU4OTExOTY4MSwianRpIjoiMmEwYmY0NWUtMjhmOS00YTUzLTlmNzItMmM5ZWVlYThkNzc2IiwiZXhwIjoxNTg5MTIwNTgxLCJpZGVudGl0eSI6eyJ1IjoiRnJlcXRyYWRlciJ9LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.qt6MAXYIa-l556OM7arBvYJ0SDI9J8bIk3_glDujF5g"
# 使用 access_token 进行身份验证
> curl -X GET --header "Authorization: Bearer ${access_token}" http://localhost:8080/api/v1/count

```

由于访问令牌的超时时间较短（15 分钟） —— 应定期使用 `token/refresh` 请求来获取新鲜的访问令牌：

``` bash
> curl -X POST --header "Authorization: Bearer ${refresh_token}"http://localhost:8080/api/v1/token/refresh
{"access_token":"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE1ODkxMTk5NzQsIm5iZiI6MTU4OTExOTk3NCwianRpIjoiMDBjNTlhMWUtMjBmYS00ZTk0LTliZjAtNWQwNTg2MTdiZDIyIiwiZXhwIjoxNTg5MTIwODc0LCJpZGVudGl0eSI6eyJ1IjoiRnJlcXRyYWRlciJ9LCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.1seHlII3WprjjclY6DpRhen0rqdF4j6jbvxIhUFaSbs"}
```

--8<-- "zh_CN/includes/cors.md"
