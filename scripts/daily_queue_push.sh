#!/bin/bash
# 每日群发队列生成脚本 - 输出结果直接作为推送内容
cd /home/ubuntu/yufeng-event-api && source .venv/bin/activate
python3 scripts/generate_queue.py 2>&1 | grep -v 'wecom\|token\|request_id\|http_status'
