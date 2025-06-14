# HTTPS/SSL 設定指南

本指南將幫助您為 AI News 應用程式設定 HTTPS 支援。

## 🔒 概述

我們的 HTTPS 解決方案包含：
- **Let's Encrypt** 免費 SSL 憑證
- **自動 HTTP 到 HTTPS 重定向**
- **現代安全標頭配置**
- **自動憑證更新機制**

## 📋 前置需求

### 生產環境
- 一個指向您伺服器的域名
- 開放的端口 80 和 443
- Docker 和 Docker Compose

### 本地開發
- Docker 和 Docker Compose
- 可接受自簽憑證的瀏覽器設定

## 🚀 快速設定

### 步驟 1: 生產環境設定

```bash
# 克隆專案（如果尚未完成）
git clone <your-repo-url>
cd ai-news

# 執行 HTTPS 設定腳本
./setup_ssl.sh yourdomain.com admin@yourdomain.com
```

### 步驟 2: 本地開發設定

```bash
# 使用 localhost 進行本地開發
./setup_ssl.sh localhost admin@localhost.local
```

## 🔧 手動設定步驟

如果您想要手動設定，請按照以下步驟：

### 1. 更新 docker-compose.yml

```yaml
# 在 certbot 服務中更新您的域名和電子郵件
command: certonly --webroot --webroot-path=/var/www/certbot --email your-email@example.com --agree-tos --no-eff-email -d your-domain.com
```

### 2. 建置並啟動服務

```bash
docker-compose down
docker-compose build
docker-compose up -d frontend
```

### 3. 獲取 SSL 憑證

```bash
# 等待前端服務啟動
sleep 10

# 執行 certbot 獲取憑證
docker-compose run --rm certbot

# 重新載入 nginx
docker-compose exec frontend nginx -s reload
```

## 🔄 憑證管理

### 自動更新設定

```bash
# 編輯 crontab
crontab -e

# 添加自動更新任務（每天中午 12 點）
0 12 * * * cd /path/to/your/project && ./renew_ssl.sh >> /var/log/ssl-renewal.log 2>&1
```

### 手動更新

```bash
# 執行更新腳本
./renew_ssl.sh

# 或者手動執行
docker-compose run --rm certbot renew
docker-compose exec frontend nginx -s reload
```

## 🛡️ 安全配置

我們的 nginx 配置包含以下安全特性：

### SSL/TLS 設定
- **協議**: TLSv1.2, TLSv1.3
- **加密套件**: 現代安全加密套件
- **會話快取**: 10 分鐘會話快取

### 安全標頭
- `Strict-Transport-Security`: 強制 HTTPS
- `X-Frame-Options`: 防止點擊劫持
- `X-Content-Type-Options`: 防止 MIME 類型嗅探
- `X-XSS-Protection`: XSS 保護
- `Referrer-Policy`: 控制 referrer 資訊

## 🔍 故障排除

### 常見問題

#### 1. 憑證獲取失敗

**症狀**: Let's Encrypt 憑證請求失敗

**解決方案**:
```bash
# 檢查域名解析
nslookup yourdomain.com

# 檢查端口 80 是否可訪問
curl -I http://yourdomain.com/.well-known/acme-challenge/test

# 檢查 certbot 日誌
docker-compose logs certbot
```

#### 2. Nginx 啟動失敗

**症狀**: Frontend 容器無法啟動

**解決方案**:
```bash
# 檢查 nginx 配置
docker-compose exec frontend nginx -t

# 檢查憑證檔案
docker-compose exec frontend ls -la /etc/letsencrypt/live/

# 重新建置容器
docker-compose build frontend
docker-compose up -d frontend
```

#### 3. 瀏覽器顯示不安全

**症狀**: 瀏覽器顯示憑證錯誤

**解決方案**:
```bash
# 檢查憑證有效期
docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout | grep -A 2 "Validity"

# 檢查憑證域名
docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout | grep "Subject Alternative Name" -A 1
```

### 日誌檢查

```bash
# 檢查所有服務日誌
docker-compose logs -f

# 檢查 nginx 錯誤日誌
docker-compose exec frontend tail -f /var/log/nginx/error.log

# 檢查 certbot 日誌
docker-compose logs certbot
```

## 📊 憑證監控

### 檢查憑證狀態

```bash
# 檢查憑證到期時間
docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -noout -dates

# 檢查憑證詳細資訊
docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout
```

### 設定監控警報

您可以設定監控腳本來檢查憑證到期時間：

```bash
#!/bin/bash
# check_ssl_expiry.sh

DOMAIN="yourdomain.com"
DAYS_BEFORE_EXPIRY=30

EXPIRY_DATE=$(docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -enddate | cut -d= -f2)
EXPIRY_TIMESTAMP=$(date -d "$EXPIRY_DATE" +%s)
CURRENT_TIMESTAMP=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_TIMESTAMP - $CURRENT_TIMESTAMP) / 86400 ))

if [ $DAYS_UNTIL_EXPIRY -lt $DAYS_BEFORE_EXPIRY ]; then
    echo "警告: SSL 憑證將在 $DAYS_UNTIL_EXPIRY 天後到期！"
    # 在這裡添加通知邏輯（例如發送電子郵件）
fi
```

## 🌐 多域名支援

如果您需要支援多個域名：

```bash
# 修改 certbot 命令以包含多個域名
command: certonly --webroot --webroot-path=/var/www/certbot --email your-email@example.com --agree-tos --no-eff-email -d domain1.com -d domain2.com -d www.domain1.com
```

## 📞 支援

如果您遇到問題：

1. 檢查本指南的故障排除章節
2. 查看專案的 GitHub Issues
3. 檢查 Let's Encrypt 的官方文檔

## 🔗 相關資源

- [Let's Encrypt 官方文檔](https://letsencrypt.org/docs/)
- [Nginx SSL 配置指南](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Mozilla SSL 配置生成器](https://ssl-config.mozilla.org/)