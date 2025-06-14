#!/bin/bash
set -e

echo "🗑️  資料庫清理工具"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查是否在專案目錄中
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}錯誤: 找不到 docker-compose.yml 檔案${NC}"
    echo "請確保您在專案根目錄中執行此腳本"
    exit 1
fi

echo -e "${BLUE}此腳本將會：${NC}"
echo "1. 停止所有 Docker 服務"
echo "2. 清理資料庫檔案"
echo "3. 重新啟動服務"
echo "4. 觸發新的資料抓取和翻譯"
echo ""

# 確認操作
read -p "⚠️  這將刪除所有現有的新聞資料，是否繼續？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}操作已取消${NC}"
    exit 0
fi

echo -e "${YELLOW}開始清理資料庫...${NC}"

# 1. 停止所有服務
echo -e "${BLUE}步驟 1: 停止 Docker 服務...${NC}"
docker-compose down

# 2. 備份現有資料庫（可選）
if [ -f "backend/app/ai_news.db" ]; then
    BACKUP_NAME="ai_news_backup_$(date +%Y%m%d_%H%M%S).db"
    echo -e "${YELLOW}備份現有資料庫到: ${BACKUP_NAME}${NC}"
    cp backend/app/ai_news.db "backup_${BACKUP_NAME}" 2>/dev/null || echo -e "${YELLOW}無法建立備份（可能是權限問題）${NC}"
fi

# 3. 清理資料庫檔案
echo -e "${BLUE}步驟 2: 清理資料庫檔案...${NC}"
if [ -f "backend/app/ai_news.db" ]; then
    rm -f backend/app/ai_news.db
    echo -e "${GREEN}✅ 資料庫檔案已刪除${NC}"
else
    echo -e "${YELLOW}資料庫檔案不存在，跳過刪除${NC}"
fi

# 4. 清理可能的快取檔案
echo -e "${BLUE}步驟 3: 清理快取檔案...${NC}"
rm -rf backend/app/__pycache__/
echo -e "${GREEN}✅ 快取檔案已清理${NC}"

# 5. 重新啟動服務
echo -e "${BLUE}步驟 4: 重新啟動服務...${NC}"
docker-compose up -d

# 6. 等待服務啟動
echo -e "${YELLOW}等待服務啟動...${NC}"
sleep 10

# 7. 檢查服務狀態
echo -e "${BLUE}步驟 5: 檢查服務狀態...${NC}"
docker-compose ps

# 8. 等待後端完全啟動
echo -e "${YELLOW}等待後端服務完全啟動...${NC}"
for i in {1..30}; do
    if curl -f http://localhost/api/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 後端服務已啟動${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ 後端服務啟動超時${NC}"
        echo "請檢查日誌: docker-compose logs backend"
        exit 1
    fi
    sleep 2
done

# 9. 觸發資料抓取
echo -e "${BLUE}步驟 6: 觸發新聞抓取和翻譯...${NC}"
echo -e "${YELLOW}正在抓取最新新聞...${NC}"

# 使用 API 觸發抓取
REFRESH_RESULT=$(curl -s -X POST http://localhost/api/refresh)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 新聞抓取請求已發送${NC}"
    echo "抓取結果: $REFRESH_RESULT"
else
    echo -e "${RED}❌ 新聞抓取請求失敗${NC}"
    echo -e "${YELLOW}嘗試手動觸發...${NC}"
    
    # 備用方法：通過調度器觸發
    TRIGGER_RESULT=$(curl -s -X POST http://localhost/api/scheduler/trigger-fetch)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 手動觸發成功${NC}"
        echo "觸發結果: $TRIGGER_RESULT"
    else
        echo -e "${RED}❌ 手動觸發也失敗${NC}"
        echo "請手動檢查服務狀態"
    fi
fi

# 10. 檢查資料庫是否重新建立
echo -e "${BLUE}步驟 7: 驗證資料庫重建...${NC}"
sleep 5

if [ -f "backend/app/ai_news.db" ]; then
    echo -e "${GREEN}✅ 新資料庫已建立${NC}"
    
    # 檢查資料庫大小
    DB_SIZE=$(ls -lh backend/app/ai_news.db | awk '{print $5}')
    echo -e "${BLUE}資料庫大小: ${DB_SIZE}${NC}"
else
    echo -e "${YELLOW}⚠️  資料庫尚未建立，可能需要更多時間${NC}"
fi

# 11. 顯示監控指令
echo -e "${GREEN}🎉 資料庫清理完成！${NC}"
echo ""
echo -e "${BLUE}監控指令：${NC}"
echo "查看服務狀態: docker-compose ps"
echo "查看後端日誌: docker-compose logs -f backend"
echo "查看抓取進度: curl http://localhost/api/articles"
echo "手動觸發抓取: curl -X POST http://localhost/api/refresh"
echo "查看翻譯統計: curl http://localhost/api/translation-stats"
echo ""

# 12. 檢查翻譯功能
echo -e "${BLUE}步驟 8: 檢查翻譯功能...${NC}"
sleep 3

STATS_RESULT=$(curl -s http://localhost/api/translation-stats)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 翻譯統計 API 正常${NC}"
    echo "統計結果: $STATS_RESULT"
else
    echo -e "${YELLOW}⚠️  翻譯統計 API 暫時無法訪問${NC}"
fi

# 13. 最終提示
echo ""
echo -e "${YELLOW}注意事項：${NC}"
echo "1. 新聞抓取和翻譯需要一些時間，請耐心等待"
echo "2. 可以通過瀏覽器訪問 http://$(curl -s ifconfig.me) 查看結果"
echo "3. 如果翻譯功能仍有問題，請檢查 OpenAI API 金鑰設置"
echo "4. 備份檔案（如果有）保存在當前目錄中"

echo -e "${GREEN}✨ 清理完成！新的資料抓取已開始...${NC}"