#!/bin/bash
set -e

echo "🔄 更新部署腳本..."

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}檢測到 Git 合併衝突，正在解決...${NC}"

# 備份現有的本地修改
if [ -f "deploy.sh" ]; then
    echo -e "${YELLOW}備份現有的 deploy.sh...${NC}"
    cp deploy.sh deploy.sh.backup
fi

# 暫存本地修改
echo -e "${YELLOW}暫存本地修改...${NC}"
git stash

# 拉取最新版本
echo -e "${YELLOW}拉取最新版本...${NC}"
git pull origin main

# 檢查是否有暫存的修改
if git stash list | grep -q "stash@{0}"; then
    echo -e "${YELLOW}發現暫存的修改，嘗試應用...${NC}"
    
    # 嘗試應用暫存的修改
    if git stash pop; then
        echo -e "${GREEN}✅ 成功合併本地修改${NC}"
    else
        echo -e "${RED}❌ 自動合併失敗，需要手動解決衝突${NC}"
        echo -e "${YELLOW}請檢查衝突檔案並手動解決，然後執行：${NC}"
        echo "git add ."
        echo "git commit -m 'Resolve merge conflicts'"
        exit 1
    fi
fi

# 確保腳本有執行權限
chmod +x deploy.sh

echo -e "${GREEN}✅ 更新完成！${NC}"
echo -e "${GREEN}現在可以執行 ./deploy.sh 進行部署${NC}"

# 如果有備份檔案，詢問是否要比較差異
if [ -f "deploy.sh.backup" ]; then
    echo ""
    read -p "是否要查看新舊版本的差異？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}新舊版本差異：${NC}"
        diff deploy.sh.backup deploy.sh || true
    fi
    
    read -p "是否要刪除備份檔案？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm deploy.sh.backup
        echo -e "${GREEN}備份檔案已刪除${NC}"
    fi
fi