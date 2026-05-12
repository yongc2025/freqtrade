#!/bin/bash

# Freqtrade 故障排查脚本
# 诊断常见问题

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# 函数：打印标题
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          Freqtrade 故障排查工具                          ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 函数：打印分隔线
print_separator() {
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
}

# 函数：检查 Docker
check_docker() {
    echo -e "${YELLOW}【检查 Docker】${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker 未安装${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Docker 已安装${NC}"
    echo "  版本: $(docker --version)"
    
    if ! docker ps > /dev/null 2>&1; then
        echo -e "${RED}✗ Docker 守护进程未运行${NC}"
        echo "  解决方案: sudo systemctl start docker"
        return 1
    fi
    
    echo -e "${GREEN}✓ Docker 守护进程运行中${NC}"
    echo ""
    return 0
}

# 函数：检查容器
check_container() {
    echo -e "${YELLOW}【检查容器】${NC}"
    
    if ! docker-compose ps | grep -q "freqtrade"; then
        echo -e "${RED}✗ 容器不存在${NC}"
        echo "  解决方案: docker-compose up -d"
        return 1
    fi
    
    STATUS=$(docker-compose ps freqtrade | awk 'NR==2 {print $NF}')
    
    if [[ $STATUS == *"Up"* ]]; then
        echo -e "${GREEN}✓ 容器运行中${NC}"
        echo "  状态: $STATUS"
    else
        echo -e "${RED}✗ 容器未运行${NC}"
        echo "  状态: $STATUS"
        echo "  解决方案: docker-compose up -d"
        return 1
    fi
    echo ""
    return 0
}

# 函数：检查资源
check_resources() {
    echo -e "${YELLOW}【检查系统资源】${NC}"
    
    # 内存
    TOTAL_MEM=$(free -h | awk 'NR==2 {print $2}')
    USED_MEM=$(free -h | awk 'NR==2 {print $3}')
    MEM_PERCENT=$(free | awk 'NR==2 {printf "%.0f", $3/$2*100}')
    
    echo "  内存: $USED_MEM / $TOTAL_MEM ($MEM_PERCENT%)"
    
    if [ $MEM_PERCENT -gt 85 ]; then
        echo -e "  ${RED}⚠ 内存使用率过高${NC}"
        echo "    解决方案:"
        echo "    1. 减少 max_open_trades"
        echo "    2. 减少交易对数量"
        echo "    3. 增加 process_throttle_secs"
    fi
    
    # CPU
    CPU_CORES=$(nproc)
    echo "  CPU 核心: $CPU_CORES"
    
    # 磁盘
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    DISK_AVAILABLE=$(df -h / | awk 'NR==2 {print $4}')
    
    echo "  磁盘: $DISK_USAGE% 已使用，$DISK_AVAILABLE 可用"
    
    if [ $DISK_USAGE -gt 85 ]; then
        echo -e "  ${RED}⚠ 磁盘空间不足${NC}"
        echo "    解决方案:"
        echo "    1. 删除旧的 OHLCV 数据"
        echo "    2. 清理日志文件"
        echo "    3. 清理 Docker 缓存: docker system prune -f"
    fi
    echo ""
}

# 函数：检查配置
check_config() {
    echo -e "${YELLOW}【检查配置文件】${NC}"
    
    if [ ! -f "user_data/config.json" ]; then
        echo -e "${RED}✗ config.json 不存在${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ config.json 存在${NC}"
    
    # 检查 JSON 格式
    if ! python3 -m json.tool user_data/config.json > /dev/null 2>&1; then
        echo -e "${RED}✗ config.json 格式错误${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ config.json 格式正确${NC}"
    
    # 检查必要字段
    if ! grep -q "exchange" user_data/config.json; then
        echo -e "${RED}✗ 缺少 exchange 配置${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ 配置字段完整${NC}"
    echo ""
    return 0
}

# 函数：检查 API
check_api() {
    echo -e "${YELLOW}【检查 API 服务】${NC}"
    
    if ! curl -s http://localhost:8080/api/v1/ping > /dev/null 2>&1; then
        echo -e "${RED}✗ API 服务无响应${NC}"
        echo "  解决方案:"
        echo "  1. 检查容器是否运行: docker-compose ps"
        echo "  2. 检查端口是否开放: netstat -tlnp | grep 8080"
        echo "  3. 查看容器日志: docker-compose logs freqtrade"
        return 1
    fi
    
    echo -e "${GREEN}✓ API 服务正常${NC}"
    
    # 获取 bot 状态
    BOT_STATUS=$(curl -s http://localhost:8080/api/v1/show_config 2>/dev/null | grep -o '"bot_name":"[^"]*"' | cut -d'"' -f4)
    if [ ! -z "$BOT_STATUS" ]; then
        echo "  Bot 名称: $BOT_STATUS"
    fi
    echo ""
    return 0
}

# 函数：检查日志错误
check_logs() {
    echo -e "${YELLOW}【检查日志错误】${NC}"
    
    if [ ! -f "user_data/logs/freqtrade.log" ]; then
        echo "  日志文件不存在"
        echo ""
        return 0
    fi
    
    # 统计错误
    ERROR_COUNT=$(grep -c "ERROR" user_data/logs/freqtrade.log 2>/dev/null || echo "0")
    WARNING_COUNT=$(grep -c "WARNING" user_data/logs/freqtrade.log 2>/dev/null || echo "0")
    
    echo "  错误数: $ERROR_COUNT"
    echo "  警告数: $WARNING_COUNT"
    
    if [ $ERROR_COUNT -gt 0 ]; then
        echo ""
        echo -e "  ${YELLOW}最近的错误:${NC}"
        grep "ERROR" user_data/logs/freqtrade.log | tail -3 | sed 's/^/    /'
    fi
    echo ""
}

# 函数：检查网络连接
check_network() {
    echo -e "${YELLOW}【检查网络连接】${NC}"
    
    # 检查互联网连接
    if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 互联网连接正常${NC}"
    else
        echo -e "${RED}✗ 互联网连接失败${NC}"
        return 1
    fi
    
    # 检查交易所连接
    if ping -c 1 api.binance.com > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Binance API 可访问${NC}"
    else
        echo -e "${RED}✗ Binance API 无法访问${NC}"
        echo "  解决方案: 检查防火墙或 VPN 设置"
        return 1
    fi
    echo ""
    return 0
}

# 函数：生成诊断报告
generate_report() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          诊断完成                                        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}【快速修复建议】${NC}"
    echo ""
    echo "常见问题解决方案:"
    echo ""
    echo "1. 容器频繁重启 (OOM)"
    echo "   - 减少 max_open_trades"
    echo "   - 减少交易对数量"
    echo "   - 增加 process_throttle_secs"
    echo ""
    echo "2. API 连接失败"
    echo "   - 检查 API 密钥是否正确"
    echo "   - 检查 IP 白名单设置"
    echo "   - 检查网络连接"
    echo ""
    echo "3. 硬盘空间不足"
    echo "   - 删除旧数据: rm -rf user_data/data/binance/*"
    echo "   - 清理日志: rm -rf user_data/logs/*.log"
    echo "   - 清理 Docker: docker system prune -f"
    echo ""
    echo "4. 策略加载失败"
    echo "   - 检查策略文件位置: ls user_data/strategies/"
    echo "   - 检查策略文件名是否与配置匹配"
    echo "   - 查看详细错误: docker-compose logs freqtrade | grep -i strategy"
    echo ""
}

# 主程序
print_header

ISSUES=0

check_docker || ((ISSUES++))
print_separator
check_container || ((ISSUES++))
print_separator
check_resources
print_separator
check_config || ((ISSUES++))
print_separator
check_api || ((ISSUES++))
print_separator
check_logs
print_separator
check_network || ((ISSUES++))
print_separator

generate_report

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过，系统运行正常${NC}"
else
    echo -e "${RED}✗ 发现 $ISSUES 个问题，请查看上面的建议${NC}"
fi
echo ""
