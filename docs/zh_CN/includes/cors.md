## CORS

整个章节仅在跨域情况下（例如您有多个运行在 `localhost:8081`、`localhost:8082` 等端口的机器人 API，并希望将它们组合到一个 FreqUI 实例中）是必要的。

??? info "技术解释"
    所有基于 Web 的前端都受 [CORS](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/CORS)（跨源资源共享）的约束。
    由于大多数对 Freqtrade API 的请求必须经过身份验证，因此正确的 CORS 策略是避免安全问题的关键。
    此外，标准不允许对带有凭据的请求使用 `*` 通配符的 CORS 策略，因此必须适当设置此设置。

用户可以通过 `CORS_origins` 配置设置允许来自不同来源 URL 的访问。
它由允许从机器人 API 消耗资源的允许 URL 列表组成。

假设您的应用程序部署为 `https://frequi.freqtrade.io/home/` —— 这意味着需要进行以下配置：

```jsonc
{
    //...
    "jwt_secret_key": "somethingrandom",
    "CORS_origins": ["https://frequi.freqtrade.io"],
    //...
}
```

在以下（非常常见的）情况下，FreqUI 可在 `http://localhost:8080/trade` 访问（这是您在导航至 FreqUI 时在导航栏中看到的内容）。
![freqUI url](../assets/frequi_url.png)

这种情况下的正确配置是 `http://localhost:8080` —— 包含端口的 URL 的主要部分。

```jsonc
{
    //...
    "jwt_secret_key": "somethingrandom",
    "CORS_origins": ["http://localhost:8080"],
    //...
}
```

!!! Tip "末尾斜杠"
    在 `CORS_origins` 配置中不允许使用末尾斜杠（例如 `"http://localhost:8080/"`）。
    这样的配置将不会生效，并且跨域错误仍将存在。

!!! Note
    我们强烈建议将 `jwt_secret_key` 设置为仅为您自己所知的随机值，以避免由于授权不足导致的机器人访问问题。
