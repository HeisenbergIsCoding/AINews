# AI News Aggregator

一個基於 FastAPI 和 React 的 AI 新聞聚合器，支援多語言翻譯和自動排程抓取。

## 功能特色

- 🔄 自動抓取多個 RSS 新聞來源
- 🌐 支援多語言翻譯（繁體中文、簡體中文、英文）
- ⏰ 自動排程任務
- 🐳 Docker 容器化部署
- 📱 響應式前端界面

## 技術架構

- **後端**: FastAPI + Python 3.11
- **前端**: React + TypeScript + Vite
- **資料庫**: SQLite
- **翻譯服務**: OpenAI API
- **部署**: Docker + Docker Compose

## 本地開發

### 前置需求

- Python 3.11+
- Node.js 18+
- OpenAI API Key

### 快速開始

1. 克隆專案
```bash
git clone <your-repo-url>
cd ai-news
```

2. 設置後端環境
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 檔案，設置 OPENAI_API_KEY
```

3. 設置前端環境
```bash
cd ../frontend
npm install
```

4. 啟動開發服務器
```bash
# 回到專案根目錄
cd ..
chmod +x start_dev.sh
./start_dev.sh
```

5. 訪問應用程式
- 前端: http://localhost:5173
- 後端 API: http://localhost:8000
- API 文檔: http://localhost:8000/docs

## AWS EC2 部署

### 步驟 1: 準備 EC2 實例

1. 在 AWS Console 建立 EC2 實例
   - AMI: Ubuntu 22.04 LTS
   - 實例類型: t3.medium 或以上
   - 安全群組: 開放端口 22 (SSH), 80 (HTTP), 443 (HTTPS)

2. 連接到 EC2 實例
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### 步驟 2: 部署應用程式

1. 克隆專案到 EC2
```bash
git clone <your-repo-url> ~/ai-news
cd ~/ai-news
```

2. 執行一鍵部署腳本
```bash
chmod +x deploy.sh
./deploy.sh
```

3. 按照腳本提示設置環境變數

### 步驟 3: 測試部署

部署完成後，您可以通過 EC2 公共 IP 訪問應用程式：
```
http://your-ec2-public-ip
```

### 步驟 4: 配置域名（可選）

1. 在 AWS Route53 建立 A 記錄
2. 指向您的 EC2 公共 IP
3. 修改 CORS 設定限制允許的來源

## Docker 指令

```bash
# 啟動服務
docker-compose up -d

# 查看服務狀態
docker-compose ps

# 查看日誌
docker-compose logs -f

# 重啟服務
docker-compose restart

# 停止服務
docker-compose down

# 重新建置並啟動
docker-compose up -d --build

# 清理未使用的資源
docker system prune -f
```

## API 端點

### 主要端點

- `GET /api/articles` - 獲取文章列表
- `POST /api/refresh` - 手動刷新新聞
- `POST /api/translate/{article_url}` - 翻譯特定文章
- `GET /api/health` - 健康檢查

### 管理端點

- `GET /api/scheduler/status` - 獲取排程器狀態
- `POST /api/scheduler/start` - 啟動排程器
- `POST /api/scheduler/stop` - 停止排程器
- `POST /api/scheduler/trigger-fetch` - 立即觸發抓取

## 環境變數

在 `backend/.env` 檔案中設置以下變數：

```env
OPENAI_API_KEY=your_openai_api_key_here
# 其他可選配置...
```

## 專案結構

```
ai-news/
├── backend/                 # 後端 FastAPI 應用程式
│   ├── app/
│   │   ├── main.py         # 主應用程式
│   │   ├── db.py           # 資料庫操作
│   │   ├── rss_fetcher.py  # RSS 抓取
│   │   └── ...
│   ├── Dockerfile          # 後端 Docker 配置
│   └── requirements.txt    # Python 依賴
├── frontend/               # 前端 React 應用程式
│   ├── src/
│   │   ├── App.tsx         # 主組件
│   │   └── ...
│   ├── Dockerfile          # 前端 Docker 配置
│   └── package.json        # Node.js 依賴
├── docker-compose.yml      # Docker Compose 配置
├── deploy.sh              # 一鍵部署腳本
└── README.md              # 專案說明
```

## 故障排除

### 常見問題

1. **服務無法啟動**
```bash
# 查看詳細日誌
docker-compose logs backend
docker-compose logs frontend
```

2. **API 請求失敗**
- 檢查 CORS 設定
- 確認後端服務正常運行
- 檢查防火牆設定

3. **翻譯功能不工作**
- 確認 OpenAI API Key 設置正確
- 檢查 API 配額和餘額

### 日誌查看

```bash
# 查看所有服務日誌
docker-compose logs -f

# 查看特定服務日誌
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 授權

MIT License