#!/usr/bin/env python3
"""
測試翻譯 API 的安全性改進
包括重複翻譯檢查和速率限制功能
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any

# 測試配置
BASE_URL = "http://localhost:8000"
TEST_ARTICLE_URL = "https://example.com/test-article"

async def test_translation_endpoint(session: aiohttp.ClientSession, article_url: str) -> Dict[str, Any]:
    """測試翻譯端點"""
    try:
        async with session.post(f"{BASE_URL}/api/translate/{article_url}") as response:
            return {
                "status_code": response.status,
                "response": await response.json(),
                "timestamp": time.time()
            }
    except Exception as e:
        return {
            "status_code": 0,
            "error": str(e),
            "timestamp": time.time()
        }

async def test_monitoring_endpoint(session: aiohttp.ClientSession) -> Dict[str, Any]:
    """測試監控端點"""
    try:
        async with session.get(f"{BASE_URL}/api/translation-monitoring") as response:
            return {
                "status_code": response.status,
                "response": await response.json()
            }
    except Exception as e:
        return {
            "status_code": 0,
            "error": str(e)
        }

async def main():
    """主測試函數"""
    print("🔒 測試翻譯 API 安全性改進")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # 測試 1: 正常翻譯請求
        print("\n📝 測試 1: 正常翻譯請求")
        result1 = await test_translation_endpoint(session, TEST_ARTICLE_URL)
        print(f"狀態碼: {result1['status_code']}")
        if 'response' in result1:
            print(f"回應: {result1['response'].get('detail', 'N/A')}")
            print(f"狀態: {result1['response'].get('status', 'N/A')}")
        
        # 測試 2: 立即重複請求（應該被速率限制或已翻譯檢查阻止）
        print("\n🔄 測試 2: 立即重複翻譯請求")
        result2 = await test_translation_endpoint(session, TEST_ARTICLE_URL)
        print(f"狀態碼: {result2['status_code']}")
        if 'response' in result2:
            print(f"回應: {result2['response'].get('detail', 'N/A')}")
            print(f"狀態: {result2['response'].get('status', 'N/A')}")
        
        # 測試 3: 快速連續請求（測試速率限制）
        print("\n⚡ 測試 3: 快速連續請求（測試速率限制）")
        for i in range(3):
            result = await test_translation_endpoint(session, f"{TEST_ARTICLE_URL}-{i}")
            print(f"請求 {i+1} - 狀態碼: {result['status_code']}")
            if 'response' in result:
                status = result['response'].get('status', 'N/A')
                detail = result['response'].get('detail', 'N/A')[:100]
                print(f"  狀態: {status}, 詳情: {detail}")
            
            # 短暫延遲
            await asyncio.sleep(0.5)
        
        # 測試 4: 檢查監控端點
        print("\n📊 測試 4: 檢查監控資訊")
        monitoring_result = await test_monitoring_endpoint(session)
        print(f"監控端點狀態碼: {monitoring_result['status_code']}")
        if 'response' in monitoring_result:
            response = monitoring_result['response']
            print(f"活躍 IP 數量: {response.get('system_status', {}).get('active_rate_limited_ips', 0)}")
            print(f"速率限制配置: {response.get('rate_limit_config', {})}")
            
            recent_stats = response.get('recent_translation_stats', {})
            print(f"最近翻譯統計:")
            print(f"  - 總請求: {recent_stats.get('total_recent_logs', 0)}")
            print(f"  - 成功: {recent_stats.get('successful_translations', 0)}")
            print(f"  - 失敗: {recent_stats.get('failed_translations', 0)}")
            print(f"  - 成功率: {recent_stats.get('success_rate', 0)}%")

    print("\n✅ 測試完成")
    print("\n💡 預期行為:")
    print("1. 第一次翻譯請求應該成功或返回 'already_translated'")
    print("2. 立即重複請求應該返回 'already_translated' 或 'rate_limited'")
    print("3. 快速連續請求應該觸發速率限制 (HTTP 429)")
    print("4. 監控端點應該顯示相關統計資訊")

if __name__ == "__main__":
    asyncio.run(main())