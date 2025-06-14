# Backend – AI News Aggregator

本目錄包含 **FastAPI** 後端服務，負責抓取多個 AI 相關 RSS、儲存於 **SQLite**，並提供 API 供前端存取。現已整合 **OpenAI 翻譯功能**，支援多語言新聞內容。

## 1. 建立與啟用 Python venv

```bash
# 進入專案根目錄
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 2. 安裝相依套件

```bash
pip install -r backend/requirements.txt
```

## 3. 設定環境變數

```bash
# 複製環境變數範本
cp backend/.env.example backend/.env

# 編輯 .env 檔案，填入您的 OpenAI API 金鑰
# OPENAI_API_KEY=your_openai_api_key_here
```

## 4. 啟動開發伺服器

```bash
uvicorn backend.app.main:app --reload --port 8000
```

* `--reload`：修改程式碼自動重新載入  
* Server 啟動後可瀏覽 <http://127.0.0.1:8000/docs> 互動式 API

## 5. API 端點

| Method | Path                    | 說明                                      |
| ------ | ----------------------- | ----------------------------------------- |
| GET    | `/articles`             | 取得所有文章 JSON<br>Query: `limit` 可限制筆數<br>現包含雙語翻譯內容 |
| POST   | `/refresh`              | 立即抓取 RSS，翻譯內容並將新文章寫入資料庫    |
| POST   | `/translate/{article_id}` | 手動觸發特定文章的翻譯                     |

### 手動更新範例

```bash
# 抓取並翻譯新文章
curl -X POST http://127.0.0.1:8000/refresh

# 翻譯特定文章 (ID=1)
curl -X POST http://127.0.0.1:8000/translate/1
```

## 6. 翻譯功能

### 翻譯邏輯
- **英文內容** → 翻譯成繁體中文
- **繁體中文內容** → 翻譯成英文
- **簡體中文內容** → 翻譯成繁體中文和英文

### 資料庫結構
新增的欄位：
- `title_zh_tw`: 繁體中文標題
- `title_en`: 英文標題
- `content_zh_tw`: 繁體中文內容
- `content_en`: 英文內容
- `original_language`: 原始語言 ('en', 'zh-tw', 'zh-cn')

### 技術特色
- 使用 OpenAI GPT-4o-mini 模型進行翻譯
- 自動語言檢測 (langdetect + OpenAI)
- 錯誤處理和重試機制
- 非同步處理提升效能

## 7. 自動排程（概念說明）

可使用下列方案排程定時更新 RSS：

* **cron** – 於 crontab 新增條目，例如每小時執行一次：
  ```cron
  0 * * * * /path/to/.venv/bin/python -m backend.app.cli.refresh
  ```
* **APScheduler** – 在 FastAPI 啟動時注入背景排程器，設定固定間隔呼叫 `fetch_all_feeds()`。

（排程程式碼尚未實作，上述為建議方向。）

## 8. 注意事項

### OpenAI API 使用
- 需要有效的 OpenAI API 金鑰
- 翻譯功能會產生 API 使用費用
- 建議設定 API 使用限制以控制成本

### 效能考量
- 翻譯是非同步處理，但仍需時間
- 大量文章翻譯可能需要較長時間
- 建議分批處理避免 API 限制

---