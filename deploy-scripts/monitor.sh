#!/bin/bash

# Freqtrade 监控脚本
# 实时显示机器人状态和资源使用情况

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 清屏
clear

# 获取项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# 函数：打印标题
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          Freqtrade 监控面板 - $(date '+%Y-%m-%d %H:%M:%S')          ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 函数：打印分隔线
print_separator() {
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
}

# 函数：检查容器状态
check_container_status() {
    echo -e "${YELLOW}【容器状态】${NC}"
    
    if docker-compose ps | grep -q "freqtrade"; then
        STATUS=$(docker-compose ps freqtrade | awk 'NR==2 {print $NF}')
        if [[ $STATUS == *"Up"* ]]; then
            echo -e "${GREEN}✓ 容器运行中${NC}"
            echo "  状态: $STATUS"
        else
            echo -e "${RED}✗ 容器未运行${NC}"
            echo "  状态: $STATUS"
        fi
    else
        echo -e "${RED}✗ 容器不存在${NC}"
    fi
    echo ""
}

# 函数：显示资源使用
show_resources() {
    echo -e "${YELLOW}【资源使用】${NC}"
    
    if docker ps | grep -q "freqtrade"; then
        STATS=$(docker stats freqtrade --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}")
        echo "$STATS" | tail -1 | awk '{print "  CPU: " $1 "\n  内存: " $2}'
    else
        echo -e "${RED}容器未运行${NC}"
    fi
    echo ""
}

# 函数：显示磁盘使用
show_disk_usage() {
    echo -e "${YELLOW}【磁盘使用】${NC}"
    
    # 数据库大小
    if [ -f "user_data/tradesv3.sqlite" ]; then
        DB_SIZE=$(du -sh user_data/tradesv3.sqlite | awk '{print $1}')
        echo "  数据库: $DB_SIZE"
    fi
    
    # 日志大小
    if [ -d "user_data/logs" ]; then
        LOG_SIZE=$(du -sh user_data/logs | awk '{print $1}')
        echo "  日志: $LOG_SIZE"
    fi
    
    # 数据大小
    if [ -d "user_data/data" ]; then
        DATA_SIZE=$(du -sh user_data/data | awk '{print $1}')
        echo "  数据: $DATA_SIZE"
    fi
    
    # 总使用
    TOTAL=$(du -sh user_data | awk '{print $1}')
    echo "  总计: $TOTAL"
    echo ""
}

# 函数：显示最近日志
show_recent_logs() {
    echo -e "${YELLOW}【最近日志】${NC}"
    
    if docker-compose ps | grep -q "freqtrade.*Up"; then
        docker-compose logs --tail=5 freqtrade | sed 's/^/  /'
    else
        echo "  容器未运行，无法获取日志"
    fi
    echo ""
}

# 函数：显示错误统计
show_error_stats() {
    echo -e "${YELLOW}【错误统计】${NC}"
    
    if [ -f "user_data/logs/freqtrade.log" ]; then
        ERROR_COUNT=$(grep -c "ERROR\|Exception" user_data/logs/freqtrade.log 2>/dev/null || echo "0")
        WARNING_COUNT=$(grep -c "WARNING" user_data/logs/freqtrade.log 2>/dev/null || echo "0")
        
        echo "  错误: $ERROR_COUNT"
        echo "  警告: $WARNING_COUNT"
    else
        echo "  日志文件不存在"
    fi
    echo ""
}

# 函数：显示 API 状态
show_api_status() {
    echo -e "${YELLOW}【API 状态】${NC}"
    
    if curl -s http://localhost:8080/api/v1/ping > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ API 服务正常${NC}"
        
        # 获取 bot 状态
        BOT_STATUS=$(curl -s http://localhost:8080/api/v1/show_config 2>/dev/null | grep -o '"bot_name":"[^"]*"' | cut -d'"' -f4)
        if [ ! -z "$BOT_STATUS" ]; then
            echo "  Bot 名称: $BOT_STATUS"
        fi
    else
        echo -e "  ${RED}✗ API 服务不可用${NC}"
    fi
    echo ""
}

# 函数：显示系统信息
show_system_info() {
    echo -e "${YELLOW}【系统信息】${NC}"
    
    # CPU 信息
    CPU_CORES=$(nproc)
    echo "  CPU 核心: $CPU_CORES"
    
    # 内存信息
    TOTAL_MEM=$(free -h | awk 'NR==2 {print $2}')
    USED_MEM=$(free -h | awk 'NR==2 {print $3}')
    echo "  内存: $USED_MEM / $TOTAL_MEM"
    
    # 磁盘信息
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
    echo "  磁盘使用率: $DISK_USAGE"
    
    # 运行时间
    UPTIME=$(uptime -p)
    echo "  运行时间: $UPTIME"
    echo ""
}

# 函数：显示建议
show_recommendations() {
    echo -e "${YELLOW}【系统建议】${NC}"
    
    # 检查磁盘空间
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 80 ]; then
        echo -e "  ${RED}⚠ 磁盘使用率超过 80%，建议清理旧数据${NC}"
    fi
    
    # 检查内存使用
    if docker ps | grep -q "freqtrade"; then
        MEM_USAGE=$(docker stats freqtrade --no-stream --format "{{.MemPerc}}" | sed 's/%//')
        if (( $(echo "$MEM_USAGE > 80" | bc -l) )); then
            echo -e "  ${RED}⚠ 内存使用率超过 80%，建议减少交易对数量${NC}"
        fi
    fi
    
    # 检查日志大小
    if [ -d "user_data/logs" ]; then
        LOG_SIZE=$(du -s user_data/logs | awk '{print $1}')
        if [ $LOG_SIZE -gt 500000 ]; then  # 500MB
            echo -e "  ${YELLOW}⚠ 日志文件过大，建议清理${NC}"
        fi
    fi
    
    echo ""
}

# 主程序
print_header
print_separator
check_container_status
print_separator
show_resources
print_separator
show_disk_usage
print_separator
show_system_info
print_separator
show_api_status
print_separator
show_error_stats
print_separator
show_recent_logs
print_separator
show_recommendations

echo -e "${BLUE}按 Ctrl+C 退出，或等待 10 秒后自动刷新...${NC}"
sleep 10

# 递归调用自己以实现实时监控
exec "$0"
