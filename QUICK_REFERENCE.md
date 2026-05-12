# Freqtrade 快速参考指南

## 目录

- [安装](#安装)
- [启动/停止](#启动停止)
- [配置](#配置)
- [监控](#监控)
- [故障排查](#故障排查)
- [常用命令](#常用命令)
- npx -y @modelcontextprotocol/inspector freqtrade-mcp

---

## 安装

### 一键部署（推荐）

```bash
# 下载并运行部署脚本
cd ~
git clone https://github.com/freqtrade/freqtrade.git
cd freqtrade
bash deploy-scripts/setup.sh
```

### 手动部署

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sudo sh

# 2. 创建项目目录
mkdir -p ~/freqtrade/user_data/{logs,strategies,backups}
cd ~/freqtrade

# 3. 复制配置文件
# 从 config_examples 复制到 user_data/config.json

# 4. 启动容器
docker-compose up -d
```

---

## 启动/停止

### 启动服务

```bash
cd ~/freqtrade
docker-compose up -d
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart freqtrade
```

### 查看状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 实时日志
docker-compose logs -f freqtrade

# 最后 100 行
docker-compose logs --tail=100 freqtrade

# 查看特定时间的日志
docker-compose logs --since 2h freqtrade
```

---

## 配置

### 编辑配置文件

```bash
# 编辑主配置
nano user_data/config.json

# 重启以应用更改
docker-compose restart freqtrade
```

### 关键配置项

| 配置项                  | 说明         | 推荐值 |
| ----------------------- | ------------ | ------ |
| `max_open_trades`       | 最大开仓数   | 2      |
| `stake_amount`          | 单笔交易金额 | 10     |
| `timeframe`             | K线周期      | 15m    |
| `dry_run`               | 模拟交易     | true   |
| `process_throttle_secs` | 进程检查间隔 | 5      |

### 添加交易对

```json
{
  "exchange": {
    "pair_whitelist": ["BTC/USDT", "ETH/USDT", "ADA/USDT"]
  }
}
```

### 配置 Telegram 通知

```json
{
  "telegram": {
    "enabled": true,
    "token": "your_bot_token",
    "chat_id": "your_chat_id"
  }
}
```

### 配置 API 服务器

```json
{
  "api_server": {
    "enabled": true,
    "listen_ip_address": "0.0.0.0",
    "listen_port": 8080,
    "username": "freqtrader",
    "password": "your_password"
  }
}
```

---

## 监控

### 实时监控面板

```bash
bash deploy-scripts/monitor.sh
```

### 查看资源使用

```bash
docker stats freqtrade
```

### 查看数据库大小

```bash
du -sh user_data/tradesv3.sqlite
```

### 查看日志大小

```bash
du -sh user_data/logs/
```

### 查看磁盘使用

```bash
df -h
```

---

## 故障排查

### 运行诊断工具

```bash
bash deploy-scripts/troubleshoot.sh
```

### 问题 1：容器无法启动

```bash
# 查看错误日志
docker-compose logs freqtrade

# 检查配置文件
python3 -m json.tool user_data/config.json

# 重新启动
docker-compose down
docker-compose up -d
```

### 问题 2：内存不足（OOM）

```bash
# 查看内存使用
docker stats freqtrade

# 解决方案：
# 1. 减少 max_open_trades
# 2. 减少交易对数量
# 3. 增加 process_throttle_secs
```

### 问题 3：API 连接失败

```bash
# 检查网络连接
ping api.binance.com

# 检查 API 密钥
# 确保密钥正确且未过期

# 查看详细错误
docker-compose logs freqtrade | grep -i "api\|error"
```

### 问题 4：硬盘空间不足

```bash
# 检查磁盘使用
df -h

# 清理旧数据
rm -rf user_data/data/binance/*

# 清理日志
rm -rf user_data/logs/*.log

# 清理 Docker
docker system prune -f
```

### 问题 5：策略加载失败

```bash
# 列出可用策略
docker-compose exec freqtrade freqtrade list-strategies

# 检查策略文件
ls -la user_data/strategies/

# 查看错误
docker-compose logs freqtrade | grep -i strategy
```

---

## 常用命令

### Docker 命令

```bash
# 查看容器
docker ps
docker-compose ps

# 查看日志
docker logs freqtrade
docker-compose logs freqtrade

# 进入容器
docker-compose exec freqtrade bash

# 停止容器
docker stop freqtrade
docker-compose down

# 删除容器
docker rm freqtrade
docker-compose down -v
```

### Freqtrade 命令

```bash
# 列出策略
docker-compose exec freqtrade freqtrade list-strategies

# 列出交易所
docker-compose exec freqtrade freqtrade list-exchanges

# 显示配置
docker-compose exec freqtrade freqtrade show-config

# 下载数据
docker-compose exec freqtrade freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT

# 回测
docker-compose exec freqtrade freqtrade backtesting --strategy SampleStrategy

# 查看交易
docker-compose exec freqtrade freqtrade show-trades
```

### 系统命令

```bash
# 查看系统信息
uname -a
free -h
df -h

# 查看进程
ps aux | grep freqtrade
docker stats

# 查看网络
netstat -tlnp | grep 8080
curl http://localhost:8080/api/v1/ping

# 查看日志
tail -f user_data/logs/freqtrade.log
grep ERROR user_data/logs/freqtrade.log
```

### 维护命令

```bash
# 运行维护脚本
bash deploy-scripts/maintenance.sh

# 备份数据库
cp user_data/tradesv3.sqlite user_data/backups/tradesv3_$(date +%Y%m%d).sqlite

# 清理旧日志
find user_data/logs -name "*.log" -mtime +7 -delete

# 清理 Docker
docker system prune -f
docker image prune -a -f
```

---

## WebUI 访问

### 地址

```text
http://your_server_ip:8080
```

### 默认凭证

- 用户名: `freqtrader`
- 密码: 在 `config.json` 中设置

### 功能

- 查看实时交易
- 查看交易历史
- 查看性能统计
- 管理策略
- 查看图表

---

## 性能优化建议

### 内存优化

```json
{
  "max_open_trades": 1,
  "stake_amount": 5,
  "internals": {
    "process_throttle_secs": 10
  }
}
```

### CPU 优化

```json
{
  "timeframe": "1h",
  "internals": {
    "process_throttle_secs": 10
  }
}
```

### 网络优化

```json
{
  "exchange": {
    "ccxt_async_config": {
      "enableRateLimit": true,
      "rateLimit": 1000
    }
  }
}
```

---

## 安全建议

### 1. 更改默认密码

```bash
# 编辑 config.json
nano user_data/config.json

# 修改 api_server.password
```

### 2. 配置防火墙

```bash
# 只允许特定 IP 访问
sudo ufw allow from 192.168.1.100 to any port 8080

# 或使用 nginx 反向代理
```

### 3. 使用 HTTPS

```bash
# 配置 nginx 反向代理
# 使用 Let's Encrypt 证书
```

### 4. 定期备份

```bash
# 每天备份
0 2 * * * cp ~/freqtrade/user_data/tradesv3.sqlite ~/freqtrade/user_data/backups/tradesv3_$(date +\%Y\%m\%d).sqlite
```

### 5. 监控日志

```bash
# 定期检查错误
grep ERROR user_data/logs/freqtrade.log
```

---

## 生产环境检查清单

- [ ] 配置了强密码
- [ ] 配置了 Telegram 通知
- [ ] 设置了防火墙规则
- [ ] 配置了定期备份
- [ ] 配置了日志轮转
- [ ] 测试了故障恢复
- [ ] 配置了监控告警
- [ ] 进行了压力测试
- [ ] 配置了 systemd 自启动
- [ ] 文档化了所有配置

---

## 获取帮助

### 官方资源

- [Freqtrade 文档](https://www.freqtrade.io)
- [GitHub Issues](https://github.com/freqtrade/freqtrade/issues)
- [Discord 社区](https://discord.gg/p7nuUNVfP7)

### 本地帮助

```bash
# 查看帮助
docker-compose exec freqtrade freqtrade --help

# 查看命令帮助
docker-compose exec freqtrade freqtrade trade --help
```

---

**最后更新**: 2026-03-30
**版本**: Freqtrade stable
