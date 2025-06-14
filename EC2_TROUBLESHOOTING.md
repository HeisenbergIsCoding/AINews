# 🔧 EC2 部署故障排除指南

## Git 拉取衝突解決

### 問題：`git pull` 時出現合併衝突

```
error: Your local changes to the following files would be overwritten by merge:
        deploy.sh
Please commit your changes or stash them before you merge.
```

### 解決方案

#### 方法一：使用更新腳本（推薦）

```bash
# 下載並執行更新腳本
curl -O https://raw.githubusercontent.com/your-username/your-repo/main/update_deployment.sh
chmod +x update_deployment.sh
./update_deployment.sh
```

#### 方法二：手動解決

```bash
# 1. 暫存本地修改
git stash

# 2. 拉取最新版本
git pull origin main

# 3. 應用暫存的修改
git stash pop

# 4. 如果有衝突，手動解決後提交
git add .
git commit -m "Resolve merge conflicts"
```

#### 方法三：重置並重新開始（簡單但會丟失本地修改）

```bash
# ⚠️ 警告：這會丟失所有本地修改
git reset --hard HEAD
git pull origin main
```

## 常見部署問題

### 1. Docker 權限問題

```bash
# 錯誤：permission denied while trying to connect to the Docker daemon
sudo usermod -aG docker $USER
# 重新登入
exit
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### 2. 端口被佔用

```bash
# 檢查端口使用情況
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :8000

# 停止佔用端口的服務
sudo systemctl stop apache2  # 如果安裝了 Apache
sudo systemctl stop nginx    # 如果有其他 Nginx 實例
```

### 3. 服務啟動失敗

```bash
# 查看詳細日誌
docker-compose logs -f backend
docker-compose logs -f frontend

# 重新建置服務
docker-compose down
docker-compose up -d --build
```

### 4. 環境變數問題

```bash
# 檢查 .env 檔案
cat backend/.env

# 確認 API 金鑰格式
# OpenAI API 金鑰應該以 sk- 開頭
```

### 5. 網路連接問題

```bash
# 檢查 EC2 安全群組
# 確保開放了以下端口：
# - 22 (SSH)
# - 80 (HTTP)
# - 443 (HTTPS)

# 測試本地連接
curl http://localhost/health
curl http://localhost/api/health
```

## 完整重新部署流程

如果遇到複雜問題，可以完全重新部署：

```bash
# 1. 停止所有服務
docker-compose down

# 2. 清理 Docker 資源
docker system prune -af
docker volume prune -f

# 3. 重新克隆專案（如果需要）
cd ~
rm -rf ai-news  # 或您的專案目錄名稱
git clone <your-repo-url> ai-news
cd ai-news

# 4. 重新部署
chmod +x deploy.sh
./deploy.sh
```

## 監控和維護

### 查看系統資源

```bash
# 查看記憶體使用
free -h

# 查看磁碟使用
df -h

# 查看 CPU 使用
top
```

### 定期維護

```bash
# 清理 Docker 資源（每週執行）
docker system prune -f

# 更新系統套件（每月執行）
sudo apt update && sudo apt upgrade -y

# 備份資料庫
cp backend/app/ai_news.db backup/ai_news_$(date +%Y%m%d).db
```

## 日誌分析

### 應用程式日誌

```bash
# 即時查看日誌
docker-compose logs -f

# 查看特定服務日誌
docker-compose logs backend
docker-compose logs frontend

# 查看最近的日誌
docker-compose logs --tail=100 backend
```

### 系統日誌

```bash
# 查看系統日誌
sudo journalctl -u docker
sudo journalctl -f  # 即時查看

# 查看 Nginx 日誌（如果直接安裝了 Nginx）
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## 效能優化

### Docker 優化

```bash
# 限制容器資源使用
# 在 docker-compose.yml 中添加：
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

### 資料庫優化

```bash
# 定期清理舊資料（如果需要）
# 可以在應用程式中添加清理邏輯
```

## 聯絡支援

如果問題仍然存在：

1. 收集錯誤日誌
2. 記錄重現步驟
3. 檢查 GitHub Issues
4. 提交新的 Issue

記住：大多數問題都可以通過重新部署解決！