#!/bin/bash
# MediaOps 生产模式启动脚本
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "=== 1. 构建前端 ==="
cd "$FRONTEND_DIR"
npm run build
echo "前端构建完成 → backend/static/"

echo ""
echo "=== 2. 启动后端 ==="
cd "$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
