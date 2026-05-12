#!/bin/bash

# Freqtrade 自动部署脚本
# 用于 2核4G 小资源服务器
# 使用方法: bash setup.sh

set -e

echo "=========================================="
echo "Freqtrade 自动部署脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}请不要以 root 身份运行此脚本${NC}"
   exit 1
fi

# 第一步：系统检查
echo -e "${YELLOW}[1/6] 系统检查...${NC}"
echo "OS: $(uname -s)"
echo "内存: $(free -h | awk 'NR==2 {print $2}')"
echo "硬盘: $(df -h / | awk 'NR==2 {print $2}')"
echo ""

# 第二步：安装依赖
echo -e "${YELLOW}[2/6] 安装系统依赖...${NC}"
sudo apt update
sudo apt install -y curl wget git

# 检查 Docker 是否已安装
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
else
    echo "Docker 已安装: $(docker --version)"
fi

# 检查 Docker Compose 是否已安装
if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose 已安装: $(docker-compose --version)"
fi

# 添加用户到 docker 组
sudo usermod -aG docker $USER
echo -e "${GREEN}✓ 系统依赖安装完成${NC}"
echo ""

# 第三步：创建项目目录
echo -e "${YELLOW}[3/6] 创建项目目录...${NC}"
PROJECT_DIR="$HOME/freqtrade"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 创建子目录
mkdir -p user_data/{logs,strategies,backtest_results,hyperopt_results,data/binance,backups}
chmod -R 755 user_data

echo -e "${GREEN}✓ 项目目录创建完成: $PROJECT_DIR${NC}"
echo ""

# 第四步：创建配置文件
echo -e "${YELLOW}[4/6] 创建配置文件...${NC}"

# 创建 config.json
cat > user_data/config.json << 'EOF'
{
    "max_open_trades": 2,
    "stake_currency": "USDT",
    "stake_amount": 10,
    "tradable_balance_ratio": 0.99,
    "fiat_display_currency": "USD",
    "dry_run": true,
    "dry_run_wallet": 1000,
    "cancel_open_orders_on_exit": false,
    "timeframe": "15m",
    "trailing_stop": false,
    "use_exit_signal": true,
    "exit_profit_only": false,
    "ignore_roi_if_entry_signal": false,
    "minimal_roi": {
        "40": 0.0,
        "30": 0.01,
        "20": 0.02,
        "0": 0.04
    },
    "stoploss": -0.10,
    "unfilledtimeout": {
        "entry": 10,
        "exit": 10,
        "exit_timeout_count": 0,
        "unit": "minutes"
    },
    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1,
        "price_last_balance": 0.0,
        "check_depth_of_market": {
            "enabled": false,
            "bids_to_ask_delta": 1
        }
    },
    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },
    "order_types": {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": false
    },
    "order_time_in_force": {
        "entry": "GTC",
        "exit": "GTC"
    },
    "exchange": {
        "name": "binance",
        "key": "your_exchange_key_here",
        "secret": "your_exchange_secret_here",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": [
            "BTC/USDT",
            "ETH/USDT"
        ],
        "pair_blacklist": [
            "BNB/.*"
        ],
        "outdated_offset": 5,
        "markets_refresh_interval": 60
    },
    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ],
    "telegram": {
        "enabled": false,
        "token": "your_telegram_token_here",
        "chat_id": "your_telegram_chat_id_here"
    },
    "api_server": {
        "enabled": true,
        "listen_ip_address": "0.0.0.0",
        "listen_port": 8080,
        "verbosity": "error",
        "jwt_secret_key": "your_secret_key_change_this",
        "CORS_origins": [],
        "username": "freqtrader",
        "password": "your_secure_password_here"
    },
    "bot_name": "freqtrade",
    "initial_state": "running",
    "force_entry_enable": false,
    "internals": {
        "process_throttle_secs": 5,
        "sd_notify": false
    }
}
EOF

echo -e "${GREEN}✓ config.json 创建完成${NC}"

# 创建 docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  freqtrade:
    image: freqtradeorg/freqtrade:stable
    container_name: freqtrade
    restart: unless-stopped
    
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1.5G
    
    volumes:
      - ./user_data:/freqtrade/user_data
    
    ports:
      - "8080:8080"
    
    environment:
      - TZ=UTC
      - PYTHONUNBUFFERED=1
    
    command: >
      trade
      --logfile /freqtrade/user_data/logs/freqtrade.log
      --db-url sqlite:////freqtrade/user_data/tradesv3.sqlite
      --config /freqtrade/user_data/config.json
      --strategy SampleStrategy
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
EOF

echo -e "${GREEN}✓ docker-compose.yml 创建完成${NC}"
echo ""

# 第五步：启动容器
echo -e "${YELLOW}[5/6] 启动 Docker 容器...${NC}"
docker-compose up -d

# 等待容器启动
echo "等待容器启动..."
sleep 10

# 检查容器状态
if docker-compose ps | grep -q "freqtrade.*Up"; then
    echo -e "${GREEN}✓ 容器启动成功${NC}"
else
    echo -e "${RED}✗ 容器启动失败${NC}"
    docker-compose logs freqtrade
    exit 1
fi
echo ""

# 第六步：显示信息
echo -e "${YELLOW}[6/6] 部署完成${NC}"
echo ""
echo -e "${GREEN}=========================================="
echo "部署成功！"
echo "==========================================${NC}"
echo ""
echo "📁 项目目录: $PROJECT_DIR"
echo "🌐 WebUI 地址: http://localhost:8080"
echo "👤 默认用户名: freqtrader"
echo "🔑 默认密码: your_secure_password_here"
echo ""
echo "⚠️  重要提示："
echo "1. 请修改 user_data/config.json 中的交易所 API 密钥"
echo "2. 请修改 API 服务器的密码"
echo "3. 请配置 Telegram 通知（可选）"
echo ""
echo "📋 常用命令："
echo "  查看日志: docker-compose logs -f freqtrade"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart freqtrade"
echo "  查看状态: docker-compose ps"
echo ""
echo "📚 更多信息请查看: DEPLOYMENT_GUIDE_CN.md"
echo ""
