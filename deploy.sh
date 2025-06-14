#!/bin/bash
set -e

echo "🚀 開始部署 AI News 應用程式到 EC2..."

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查是否為 root 用戶
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}請不要使用 root 用戶執行此腳本${NC}"
    exit 1
fi

# 檢查 Docker 是否已安裝
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}正在安裝 Docker...${NC}"
    sudo apt update
    sudo apt install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo -e "${RED}Docker 已安裝，請重新登入以套用權限，然後重新執行此腳本${NC}"
    exit 1
fi

# 檢查 Docker Compose 是否已安裝
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}正在安裝 Docker Compose...${NC}"
    sudo apt install -y docker-compose
fi

# 檢查是否在專案目錄中
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}錯誤: 找不到 docker-compose.yml 檔案${NC}"
    echo "請確保您在專案根目錄中執行此腳本"
    exit 1
fi

# 檢查環境變數檔案
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}正在建立環境變數檔案...${NC}"
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        echo -e "${YELLOW}請編輯 backend/.env 檔案設置您的 OpenAI API 金鑰${NC}"
        echo -e "${YELLOW}您需要將 'your_openai_api_key_here' 替換為您的實際 API 金鑰${NC}"
        read -p "按 Enter 繼續編輯環境變數檔案..."
        nano backend/.env
        
        # 檢查是否已設置 API 金鑰
        if grep -q "your_openai_api_key_here" backend/.env; then
            echo -e "${RED}警告: 您尚未設置 OpenAI API 金鑰！${NC}"
            echo -e "${RED}請確保已將 'your_openai_api_key_here' 替換為您的實際 API 金鑰${NC}"
            read -p "是否要重新編輯？(y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                nano backend/.env
            fi
        fi
    else
        echo -e "${RED}錯誤: 找不到 backend/.env.example 檔案${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}找到現有的 .env 檔案${NC}"
    # 檢查現有檔案是否包含預設值
    if grep -q "your_openai_api_key_here" backend/.env; then
        echo -e "${YELLOW}檢測到 .env 檔案包含預設值，請更新您的 API 金鑰${NC}"
        read -p "是否要編輯 .env 檔案？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            nano backend/.env
        fi
    fi
fi

# 停止現有服務
echo -e "${YELLOW}停止現有服務...${NC}"
docker-compose down 2>/dev/null || true

# 清理舊的映像檔（可選）
read -p "是否要清理舊的 Docker 映像檔？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}清理舊的映像檔...${NC}"
    docker system prune -f
fi

# 建置並啟動服務
echo -e "${YELLOW}建置並啟動服務...${NC}"
docker-compose up -d --build

# 等待服務啟動
echo -e "${YELLOW}等待服務啟動...${NC}"
sleep 10

# 檢查服務狀態
echo -e "${YELLOW}檢查服務狀態...${NC}"
docker-compose ps

# 檢查服務健康狀態
echo -e "${YELLOW}檢查服務健康狀態...${NC}"
for i in {1..30}; do
    if curl -f http://localhost/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 前端服務正常運行${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ 前端服務啟動失敗${NC}"
        docker-compose logs frontend
        exit 1
    fi
    sleep 2
done

for i in {1..30}; do
    if curl -f http://localhost/api/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 後端服務正常運行${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ 後端服務啟動失敗${NC}"
        docker-compose logs backend
        exit 1
    fi
    sleep 2
done

# 獲取 EC2 公共 IP
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com/ || curl -s http://ifconfig.me/ || echo "無法獲取公共 IP")

echo -e "${GREEN}🎉 部署完成！${NC}"
echo -e "${GREEN}您可以通過以下網址訪問應用程式:${NC}"
echo -e "${GREEN}http://${PUBLIC_IP}${NC}"
echo ""
echo -e "${YELLOW}常用管理指令:${NC}"
echo "查看服務狀態: docker-compose ps"
echo "查看日誌: docker-compose logs -f"
echo "重啟服務: docker-compose restart"
echo "停止服務: docker-compose down"
echo "更新應用程式: git pull && docker-compose up -d --build"
echo ""
echo -e "${YELLOW}注意事項:${NC}"
echo "1. 確保 EC2 安全群組已開放 80 端口"
echo "2. 測試完成後，請修改 CORS 設定限制允許的來源"
echo "3. 建議設置 SSL 憑證以使用 HTTPS"