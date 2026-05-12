#!/bin/bash

# Freqtrade 维护脚本
# 定期清理、备份和优化

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

# 日志文件
LOG_FILE="user_data/logs/maintenance.log"

# 函数：记录日志
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 函数：打印标题
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          Freqtrade 维护脚本                              ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 函数：清理旧日志
cleanup_old_logs() {
    echo -e "${YELLOW}[1/5] 清理旧日志...${NC}"
    
    if [ -d "user_data/logs" ]; then
        # 删除 7 天前的日志
        find user_data/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
        
        # 压缩当前日志（如果超过 50MB）
        if [ -f "user_data/logs/freqtrade.log" ]; then
            SIZE=$(stat -f%z "user_data/logs/freqtrade.log" 2>/dev/null || stat -c%s "user_data/logs/freqtrade.log" 2>/dev/null || echo "0")
            if [ $SIZE -gt 52428800 ]; then  # 50MB
                gzip -c "user_data/logs/freqtrade.log" > "user_data/logs/freqtrade_$(date +%Y%m%d).log.gz"
                > "user_data/logs/freqtrade.log"  # 清空日志
                log_message "✓ 日志已压缩和清空"
            fi
        fi
        
        echo -e "${GREEN}✓ 旧日志清理完成${NC}"
    fi
    echo ""
}

# 函数：备份数据库
backup_database() {
    echo -e "${YELLOW}[2/5] 备份数据库...${NC}"
    
    if [ -f "user_data/tradesv3.sqlite" ]; then
        mkdir -p user_data/backups
        
        BACKUP_FILE="user_data/backups/tradesv3_$(date +%Y%m%d_%H%M%S).sqlite"
        cp user_data/tradesv3.sqlite "$BACKUP_FILE"
        
        # 只保留最近 7 个备份
        ls -t user_data/backups/tradesv3_*.sqlite 2>/dev/null | tail -n +8 | xargs -r rm
        
        log_message "✓ 数据库已备份: $BACKUP_FILE"
        echo -e "${GREEN}✓ 数据库备份完成${NC}"
    fi
    echo ""
}

# 函数：清理 Docker 缓存
cleanup_docker() {
    echo -e "${YELLOW}[3/5] 清理 Docker 缓存...${NC}"
    
    # 删除未使用的镜像和容器
    docker system prune -f > /dev/null 2>&1 || true
    
    log_message "✓ Docker 缓存已清理"
    echo -e "${GREEN}✓ Docker 缓存清理完成${NC}"
    echo ""
}

# 函数：检查磁盘空间
check_disk_space() {
    echo -e "${YELLOW}[4/5] 检查磁盘空间...${NC}"
    
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    DISK_AVAILABLE=$(df -h / | awk 'NR==2 {print $4}')
    
    echo "  磁盘使用率: ${DISK_USAGE}%"
    echo "  可用空间: $DISK_AVAILABLE"
    
    if [ $DISK_USAGE -gt 85 ]; then
        echo -e "  ${RED}⚠ 警告：磁盘使用率超过 85%${NC}"
        log_message "⚠ 警告：磁盘使用率超过 85%"
        
        # 尝试清理旧数据
        echo "  尝试清理旧数据..."
        find user_data/data -name "*.feather" -mtime +30 -delete 2>/dev/null || true
        find user_data/data -name "*.csv" -mtime +30 -delete 2>/dev/null || true
    else
        echo -e "  ${GREEN}✓ 磁盘空间充足${NC}"
    fi
    echo ""
}

# 函数：检查容器健康状态
check_container_health() {
    echo -e "${YELLOW}[5/5] 检查容器健康状态...${NC}"
    
    if docker-compose ps | grep -q "freqtrade"; then
        STATUS=$(docker-compose ps freqtrade | awk 'NR==2 {print $NF}')
        
        if [[ $STATUS == *"Up"* ]]; then
            echo -e "  ${GREEN}✓ 容器运行正常${NC}"
            log_message "✓ 容器运行正常"
            
            # 检查 API 是否响应
            if curl -s http://localhost:8080/api/v1/ping > /dev/null 2>&1; then
                echo -e "  ${GREEN}✓ API 服务正常${NC}"
                log_message "✓ API 服务正常"
            else
                echo -e "  ${RED}✗ API 服务无响应${NC}"
                log_message "✗ API 服务无响应"
            fi
        else
            echo -e "  ${RED}✗ 容器状态异常: $STATUS${NC}"
            log_message "✗ 容器状态异常: $STATUS"
        fi
    else
        echo -e "  ${RED}✗ 容器未运行${NC}"
        log_message "✗ 容器未运行"
    fi
    echo ""
}

# 函数：生成报告
generate_report() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          维护完成                                        ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}【维护统计】${NC}"
    
    # 数据库大小
    if [ -f "user_data/tradesv3.sqlite" ]; then
        DB_SIZE=$(du -sh user_data/tradesv3.sqlite | awk '{print $1}')
        echo "  数据库大小: $DB_SIZE"
    fi
    
    # 日志大小
    if [ -d "user_data/logs" ]; then
        LOG_SIZE=$(du -sh user_data/logs | awk '{print $1}')
        echo "  日志大小: $LOG_SIZE"
    fi
    
    # 备份数量
    BACKUP_COUNT=$(ls -1 user_data/backups/tradesv3_*.sqlite 2>/dev/null | wc -l)
    echo "  备份数量: $BACKUP_COUNT"
    
    # 总使用空间
    TOTAL=$(du -sh user_data | awk '{print $1}')
    echo "  总使用空间: $TOTAL"
    
    echo ""
    echo -e "${GREEN}维护日志已保存到: $LOG_FILE${NC}"
    echo ""
}

# 主程序
print_header

# 检查是否有参数
if [ "$1" == "--full" ]; then
    echo "执行完整维护..."
    log_message "========== 完整维护开始 =========="
else
    echo "执行快速维护..."
    log_message "========== 快速维护开始 =========="
fi

cleanup_old_logs
backup_database
cleanup_docker
check_disk_space
check_container_health

generate_report

log_message "========== 维护完成 =========="
