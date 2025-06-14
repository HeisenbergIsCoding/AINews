# AI News Frontend

基於 **Vite + React + TypeScript** 的簡易前端，串接後端 FastAPI 服務。

## 開發

```bash
cd frontend
npm install
npm run dev
```

- 預設開發伺服器埠號：<http://localhost:5173>
- 已於 `vite.config.ts` 設定 proxy，將 `/api` 轉發至 `http://localhost:8000`，並移除 `/api` 前綴。

## 建置與預覽

```bash
npm run build      # 產生靜態檔案
npm run preview    # 本地預覽 production build
```

## 注意

若後端 FastAPI 以 `uvicorn backend.app.main:app --reload` 啟動於 `8000` 埠，  
則前端開發模式可自動代理；若直接部署靜態檔亦可依 CORS 設定透過瀏覽器存取。