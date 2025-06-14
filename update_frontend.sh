#!/bin/bash

# 前端 Docker 更新腳本
# 用於解決 Docker Compose 1.29.2 的 ContainerConfig 錯誤

echo "🚀 開始更新前端 Docker 容器..."

# 1. 建構新的前端映像檔
echo "📦 建構新的前端映像檔..."
docker build -t ainews_frontend:latest ./frontend

if [ $? -ne 0 ]; then
    echo "❌ 前端映像檔建構失敗！"
    exit 1
fi

echo "✅ 前端映像檔建構成功"

# 2. 停止並移除現有的前端容器
echo "🛑 停止並移除現有的前端容器..."
docker stop ai-news-frontend 2>/dev/null || echo "容器已經停止"
docker rm ai-news-frontend 2>/dev/null || echo "容器已經移除"

echo "✅ 舊容器已清理"

# 3. 啟動新的前端容器
echo "🔄 啟動新的前端容器..."
docker-compose up -d frontend

if [ $? -ne 0 ]; then
    echo "❌ 前端容器啟動失敗！"
    exit 1
fi

echo "✅ 前端更新完成！"
echo "🌐 前端服務現在運行在 http://localhost 和 https://localhost"

# 4. 顯示容器狀態
echo "📊 容器狀態："
docker ps | grep ai-news-frontend