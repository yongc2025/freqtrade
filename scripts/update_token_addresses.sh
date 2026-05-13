#!/bin/bash
# 每天更新 token_addresses.json
# 用法: crontab -e → 0 8 * * * /path/to/scripts/update_token_addresses.sh

cd "$(dirname "$0")/.."
python scripts/fetch_token_addresses.py >> user_data/logs/token_update.log 2>&1
