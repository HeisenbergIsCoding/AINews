# 🐳 Docker 除錯指南

## 📋 快速診斷指令

### 基本狀態檢查

```bash
# 查看所有容器狀態
docker-compose ps

# 查看容器詳細信息
docker ps -a

# 查看 Docker 系統信息
docker system df
```

## 📊 日誌查看

### 查看所有服務日誌

```bash
# 查看所有服務的即時日誌
docker-compose logs -f

# 查看所有服務的最近日誌
docker-compose logs --tail=100

# 查看特定時間範圍的日誌
docker-compose logs --since="2024-01-01T00:00:00" --until="2024-01-01T23:59:59"
```

### 查看特定服務日誌

```bash
# 查看後端日誌
docker-compose logs backend
docker-compose logs -f backend  # 即時查看

# 查看前端日誌
docker-compose logs frontend
docker-compose logs -f frontend  # 即時查看

# 查看最近 50 行日誌
docker-compose logs --tail=50 backend
docker-compose logs --tail=50 frontend
```

### 進階日誌查看

```bash
# 查看容器內部日誌檔案
docker-compose exec backend ls -la /var/log/
docker-compose exec frontend ls -la /var/log/nginx/

# 查看 Nginx 訪問日誌
docker-compose exec frontend tail -f /var/log/nginx/access.log

# 查看 Nginx 錯誤日誌
docker-compose exec frontend tail -f /var/log/nginx/error.log
```

## 🔍 容器內部檢查

### 進入容器內部

```bash
# 進入後端容器
docker-compose exec backend bash
# 或者如果沒有 bash
docker-compose exec backend sh

# 進入前端容器
docker-compose exec frontend sh
```

### 檢查容器內部狀態

```bash
# 檢查後端容器內部
docker-compose exec backend ls -la /app/
docker-compose exec backend ls -la /app/app/
docker-compose exec backend cat /app/.env
docker-compose exec backend env | grep OPENAI

# 檢查前端容器內部
docker-compose exec frontend ls -la /usr/share/nginx/html/
docker-compose exec frontend nginx -t  # 檢查 Nginx 配置
docker-compose exec frontend ps aux    # 檢查運行的程序
```

## 🌐 網路和連接測試

### 測試服務連接

```bash
# 測試前端健康檢查
curl -v http://localhost/health
curl -v http://localhost:80/health

# 測試後端健康檢查
curl -v http://localhost/api/health
curl -v http://localhost:8000/api/health

# 測試 API 端點
curl -v http://localhost/api/articles
curl -X POST http://localhost/api/refresh
```

### 容器間網路測試

```bash
# 從前端容器測試後端連接
docker-compose exec frontend curl -v http://backend:8000/api/health

# 從後端容器測試自身
docker-compose exec backend curl -v http://localhost:8000/api/health
```

## 🔧 常見問題診斷

### 1. 容器啟動失敗

```bash
# 查看容器退出原因
docker-compose ps
docker inspect ai-news-backend
docker inspect ai-news-frontend

# 查看詳細錯誤信息
docker-compose logs backend | grep -i error
docker-compose logs frontend | grep -i error
```

### 2. 健康檢查失敗

```bash
# 手動執行健康檢查
docker-compose exec backend curl -f http://localhost:8000/api/health
docker-compose exec frontend curl -f http://localhost:80/health

# 檢查健康檢查配置
docker inspect ai-news-backend | grep -A 10 -B 5 "Health"
docker inspect ai-news-frontend | grep -A 10 -B 5 "Health"
```

### 3. 環境變數問題

```bash
# 檢查環境變數是否正確載入
docker-compose exec backend env
docker-compose exec backend env | grep OPENAI
docker-compose exec backend printenv OPENAI_API_KEY

# 檢查 .env 檔案
ls -la backend/.env
cat backend/.env
```

### 4. 資料庫問題

```bash
# 檢查資料庫檔案
ls -la backend/app/ai_news.db
docker-compose exec backend ls -la /app/app/ai_news.db

# 檢查資料庫權限
docker-compose exec backend stat /app/app/ai_news.db
```

### 5. 端口衝突

```bash
# 檢查端口使用情況
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :8000
sudo lsof -i :80
sudo lsof -i :8000
```

## 🚀 重建和重啟

### 重啟服務

```bash
# 重啟所有服務
docker-compose restart

# 重啟特定服務
docker-compose restart backend
docker-compose restart frontend
```

### 重新建置

```bash
# 重新建置所有服務
docker-compose build --no-cache
docker-compose up -d --build

# 重新建置特定服務
docker-compose build --no-cache backend
docker-compose build --no-cache frontend
```

### 完全清理重建

```bash
# 停止並刪除所有容器
docker-compose down -v

# 清理所有 Docker 資源
docker system prune -af
docker volume prune -f

# 重新建置並啟動
docker-compose up -d --build
```

## 📈 效能監控

### 資源使用情況

```bash
# 查看容器資源使用
docker stats

# 查看特定容器資源使用
docker stats ai-news-backend ai-news-frontend

# 查看系統資源
free -h
df -h
top
```

### 容器詳細信息

```bash
# 查看容器詳細配置
docker inspect ai-news-backend
docker inspect ai-news-frontend

# 查看容器網路信息
docker network ls
docker network inspect ai-news_ai-news-network
```

## 🔄 故障排除流程

### 標準診斷流程

```bash
# 1. 檢查容器狀態
docker-compose ps

# 2. 查看日誌
docker-compose logs --tail=50

# 3. 檢查健康狀態
curl http://localhost/health
curl http://localhost/api/health

# 4. 檢查環境變數
docker-compose exec backend env | grep OPENAI

# 5. 檢查檔案權限
ls -la backend/app/
docker-compose exec backend ls -la /app/app/

# 6. 如果問題持續，重新建置
docker-compose down
docker-compose up -d --build
```

## 📝 日誌分析技巧

### 過濾和搜尋日誌

```bash
# 搜尋錯誤信息
docker-compose logs | grep -i error
docker-compose logs | grep -i warning
docker-compose logs | grep -i failed

# 搜尋特定關鍵字
docker-compose logs | grep -i "openai"
docker-compose logs | grep -i "database"
docker-compose logs | grep -i "翻譯"

# 統計錯誤數量
docker-compose logs | grep -c -i error
```

### 匯出日誌

```bash
# 匯出所有日誌到檔案
docker-compose logs > docker_logs_$(date +%Y%m%d_%H%M%S).log

# 匯出特定服務日誌
docker-compose logs backend > backend_logs_$(date +%Y%m%d_%H%M%S).log
docker-compose logs frontend > frontend_logs_$(date +%Y%m%d_%H%M%S).log
```

## 🆘 緊急修復指令

```bash
# 一鍵診斷腳本
echo "=== Docker 容器狀態 ==="
docker-compose ps
echo -e "\n=== 最近日誌 ==="
docker-compose logs --tail=20
echo -e "\n=== 健康檢查 ==="
curl -s http://localhost/health || echo "前端健康檢查失敗"
curl -s http://localhost/api/health || echo "後端健康檢查失敗"
echo -e "\n=== 環境變數檢查 ==="
docker-compose exec backend env | grep OPENAI || echo "環境變數檢查失敗"
```

使用這些指令可以快速診斷和解決大部分 Docker 相關問題！