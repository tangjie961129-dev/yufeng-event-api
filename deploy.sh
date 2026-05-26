#!/bin/bash
# 屿风活动报名小程序 - 一键部署脚本
# 在本地 WSL 运行

set -e

SERVER="ubuntu@106.53.168.186"
PROJECT_DIR="/home/ubuntu/yufeng-event-api"

echo "=== 1. 创建服务器数据库 ==="
ssh "$SERVER" "echo 'CREATE DATABASE yufeng;' | psql -U gbrain -h localhost -p 5432 -d postgres 2>/dev/null || echo '数据库可能已存在'"

echo "=== 2. 同步项目文件 ==="
rsync -avz --delete \
  --exclude '.env' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '*.pyc' \
  ./yufeng-event-api/ "$SERVER:$PROJECT_DIR/"

echo "=== 3. 安装依赖 ==="
ssh "$SERVER" "source ~/yufeng-event-venv/bin/activate && pip install -r $PROJECT_DIR/requirements.txt"

echo "=== 4. 配置 .env ==="
echo "请手动将 .env 文件传到服务器: scp .env $SERVER:$PROJECT_DIR/.env"

echo "=== 5. 配置 systemd 服务 ==="
ssh "$SERVER" "sudo cp $PROJECT_DIR/yufeng-event-api.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable yufeng-event-api && sudo systemctl restart yufeng-event-api"

echo "=== 6. 验证 ==="
sleep 3
ssh "$SERVER" "sudo systemctl status yufeng-event-api --no-pager | head -10"
curl -s "http://$SERVER:8000/health" || echo "等待服务启动..."

echo "=== 部署完成 ==="
