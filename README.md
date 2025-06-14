# AI News Aggregator

一個基於 FastAPI 和 React 的智能新聞聚合器，支援多語言翻譯和自動排程抓取。

## ✨ 功能特色

- 🔄 **自動抓取** - 支援多個 RSS 新聞來源的自動抓取
- 🌐 **智能翻譯** - 使用 OpenAI API 進行多語言翻譯（繁體中文、簡體中文、英文）
- ⏰ **排程任務** - 自動化新聞抓取和翻譯排程
- 🐳 **容器化部署** - 完整的 Docker 容器化解決方案
- 📱 **響應式界面** - 現代化的 React 前端界面
- 🔒 **HTTPS 支援** - 內建 SSL/TLS 安全連線支援
- 📊 **監控統計** - 翻譯統計和系統健康檢查

## 🏗️ 技術架構

### 後端技術棧
- **框架**: FastAPI (Python 3.11+)
- **資料庫**: SQLite with aiosqlite
- **翻譯服務**: OpenAI API
- **排程器**: APScheduler
- **RSS 解析**: feedparser

### 前端技術棧
- **框架**: React 18 + TypeScript
- **建置工具**: Vite 5
- **網頁伺服器**: Nginx

### 部署技術
- **容器化**: Docker + Docker Compose
- **SSL 憑證**: Let's Encrypt (Certbot)
- **反向代理**: Nginx

## 🚀 快速開始

### 前置需求

- Docker 和 Docker Compose
- OpenAI API Key

### 本地開發

1. **克隆專案**
```bash
git clone <your-repo-url>
cd ai_news
```

2. **設置環境變數**
```bash
cp backend/.env.example backend/.env
# 編輯 backend/.env 檔案，設置您的 OPENAI_API_KEY
```

3. **啟動開發環境**
```bash
# 使用 Docker Compose
docker-compose up -d

# 或使用開發腳本（需要本地 Python 和 Node.js 環境）
chmod +x start_dev.sh
./start_dev.sh
```

4. **訪問應用程式**
- 前端界面: http://localhost (Docker) 或 http://localhost:5173 (開發模式)
- 後端 API: http://localhost/api (Docker) 或 http://localhost:8000 (開發模式)
- API 文檔: http://localhost/api/docs

## 🌐 生產環境部署

### AWS EC2 一鍵部署

1. **準備 EC2 實例**
   - AMI: Ubuntu 22.04 LTS
   - 實例類型: t3.medium 或以上
   - 安全群組: 開放 22 (SSH), 80 (HTTP), 443 (HTTPS)

2. **執行部署腳本**
```bash
chmod +x deploy.sh
./deploy.sh
```

### HTTPS/SSL 設定

```bash
# 設定 SSL 憑證（需要域名）
./setup_ssl.sh yourdomain.com admin@yourdomain.com

# 更新 SSL 憑證
./renew_ssl.sh
```

## 📡 API 端點

### 核心功能
- `GET /api/articles` - 獲取文章列表
- `POST /api/refresh` - 手動刷新新聞
- `POST /api/batch-translate` - 批量翻譯文章
- `GET /api/health` - 系統健康檢查

### 排程管理
- `GET /api/scheduler/status` - 獲取排程器狀態
- `POST /api/scheduler/start` - 啟動排程器
- `POST /api/scheduler/stop` - 停止排程器
- `POST /api/scheduler/trigger-fetch` - 立即觸發抓取

### 統計與管理
- `GET /api/translation-stats` - 翻譯統計資訊
- `POST /api/cleanup-duplicates` - 清理重複文章

## 🔧 開發指南

### 專案結構
```
ai_news/
├── backend/                    # FastAPI 後端
│   ├── app/
│   │   ├── main.py            # 主應用程式和 API 路由
│   │   ├── db.py              # 資料庫操作
│   │   ├── rss_fetcher.py     # RSS 抓取邏輯
│   │   ├── translation_service.py  # OpenAI 翻譯服務
│   │   ├── scheduler.py       # 自動排程器
│   │   └── feeds.py           # RSS 來源配置
│   ├── Dockerfile             # 後端容器配置
│   ├── requirements.txt       # Python 依賴
│   └── .env.example          # 環境變數範例
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── App.tsx           # 主應用程式組件
│   │   ├── api.ts            # API 呼叫邏輯
│   │   └── components/       # React 組件
│   ├── Dockerfile            # 前端容器配置
│   ├── nginx.conf            # Nginx 配置
│   └── package.json          # Node.js 依賴
├── docker-compose.yml         # Docker Compose 配置
├── deploy.sh                 # 生產環境部署腳本
├── start_dev.sh              # 本地開發啟動腳本
├── setup_ssl.sh              # SSL 憑證設定腳本
├── renew_ssl.sh              # SSL 憑證更新腳本
├── clean_database.sh         # 資料庫清理工具
└── README.md                 # 專案說明文件
```

### 開發流程

#### 程式碼修改後的重新部署

**後端程式碼修改**（[`main.py`](backend/app/main.py:1)、[`rss_fetcher.py`](backend/app/rss_fetcher.py:1) 等）：
```bash
docker-compose restart backend
```

**前端程式碼修改**（[`App.tsx`](frontend/src/App.tsx:1)、CSS 等）：
```bash
docker-compose up -d --build frontend
```

**依賴檔案修改**：
```bash
# 後端依賴 (requirements.txt)
docker-compose up -d --build backend

# 前端依賴 (package.json)
docker-compose up -d --build frontend
```

#### 常用開發指令
```bash
# 查看服務狀態
docker-compose ps

# 查看即時日誌
docker-compose logs -f

# 查看特定服務日誌
docker-compose logs -f backend
docker-compose logs -f frontend

# 進入容器除錯
docker-compose exec backend bash
docker-compose exec frontend sh

# 重新建置所有服務
docker-compose down
docker-compose up -d --build
```

## 🔒 安全性配置

### 環境變數設定
在 [`backend/.env`](backend/.env.example:1) 檔案中設置：
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 重要安全提醒
⚠️ **請確保：**
- `.env` 檔案已被 `.gitignore` 忽略
- 只有 `.env.example` 會被上傳到版本控制
- 真實的 API 金鑰絕不會出現在程式碼中

## 🛠️ 維護工具

### 資料庫管理
```bash
# 清理並重置資料庫
./clean_database.sh

# 手動觸發新聞抓取
curl -X POST http://localhost/api/refresh

# 查看翻譯統計
curl http://localhost/api/translation-stats
```

### SSL 憑證管理
```bash
# 檢查憑證狀態
docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout | grep -A 2 "Validity"

# 手動更新憑證
./renew_ssl.sh

# 設定自動更新（crontab）
0 12 * * * cd /path/to/project && ./renew_ssl.sh >> /var/log/ssl-renewal.log 2>&1
```

## 🐛 故障排除

### 常見問題

1. **服務無法啟動**
```bash
docker-compose logs backend
docker-compose logs frontend
```

2. **翻譯功能不工作**
   - 檢查 OpenAI API Key 設置
   - 確認 API 配額和餘額
   - 查看後端日誌中的錯誤訊息

3. **SSL 憑證問題**
   - 確保域名正確指向伺服器 IP
   - 檢查防火牆設定（端口 80, 443）
   - 注意 Let's Encrypt 限制（每週最多 5 次失敗嘗試）

### 監控指令
```bash
# 系統健康檢查
curl http://localhost/api/health

# 檢查排程器狀態
curl http://localhost/api/scheduler/status

# 查看文章數量
curl http://localhost/api/articles | jq '.total'
```

## 📈 效能優化

- 使用 SQLite 進行輕量級資料存儲
- 實施翻譯速率限制避免 API 超額
- 支援批量翻譯提高效率
- 自動清理重複文章
- 健康檢查確保服務穩定性

## 🤝 貢獻指南

1. Fork 專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request