from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional
from collections import defaultdict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .db import fetch_articles, init_db, get_translation_stats, ensure_url_uniqueness
from .rss_fetcher import fetch_and_store_news, translate_missing_articles, refresh_feeds_fast
from .scheduler import get_scheduler, start_scheduler, stop_scheduler

# 載入環境變數
load_dotenv()

# IP 速率限制追蹤
translation_requests = defaultdict(list)  # IP -> [timestamp, ...]
TRANSLATION_RATE_LIMIT = 5  # 每小時最多5次翻譯請求
RATE_LIMIT_WINDOW = 3600  # 1小時（秒）

def check_rate_limit(client_ip: str) -> bool:
    """檢查 IP 是否超過速率限制"""
    current_time = time.time()
    
    # 清理過期的請求記錄
    translation_requests[client_ip] = [
        timestamp for timestamp in translation_requests[client_ip]
        if current_time - timestamp < RATE_LIMIT_WINDOW
    ]
    
    # 檢查是否超過限制
    if len(translation_requests[client_ip]) >= TRANSLATION_RATE_LIMIT:
        return False
    
    # 記錄新的請求
    translation_requests[client_ip].append(current_time)
    return True

app = FastAPI(
    title="AI News Aggregator",
    description="Aggregates AI-related news from several RSS feeds.",
    version="0.1.0",
)

# Enable CORS for development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",  # Alternative dev server port
        "http://127.0.0.1:3000",
        "*",  # Allow all origins for testing (change this in production)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """
    Initialize the database and start scheduler when the application starts.
    """
    await init_db()
    await start_scheduler()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """
    Stop scheduler when the application shuts down.
    """
    await stop_scheduler()


@app.get("/api/articles")
async def get_articles(
    limit: Optional[int] = Query(None, gt=0),
    language: str = Query("zh_tw", description="Language for articles (zh_tw, zh_cn, en, original)")
) -> Dict[str, Any]:
    """
    Retrieve articles from the database with all language versions for frontend language switching.

    Query Args:
        limit: Optional maximum number of articles to return (must be > 0).
        language: Language preference for fallback content (zh_tw, zh_cn, en, original).

    Returns:
        JSON payload containing a list of articles with all language versions.
    """
    try:
        # 驗證語言參數
        valid_languages = ["zh_tw", "zh_cn", "en", "original"]
        if language not in valid_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language. Must be one of: {', '.join(valid_languages)}"
            )
        
        # 獲取原始文章數據（包含所有語言版本）
        articles = await fetch_articles(limit=limit, language="original", include_untranslated=True)
        
        # 構建包含所有語言版本的文章數據
        cleaned_articles = []
        for article in articles:
            # 根據語言偏好選擇主要顯示的標題和內容
            if language == "zh_tw":
                primary_title = article.get("title_zh_tw") or article["original_title"]
                primary_content = article.get("summary_zh_tw") or article["original_summary"]
            elif language == "zh_cn":
                primary_title = article.get("title_zh_cn") or article["original_title"]
                primary_content = article.get("summary_zh_cn") or article["original_summary"]
            elif language == "en":
                primary_title = article.get("title_en") or article["original_title"]
                primary_content = article.get("summary_en") or article["original_summary"]
            else:  # original
                primary_title = article["original_title"]
                primary_content = article["original_summary"]
            
            cleaned_article = {
                "link": article["link"],
                "title": primary_title,
                "summary": primary_content,
                "published": article["published"],
                "feed_source": article["feed_source"],
                # 包含所有語言版本供前端語言切換使用
                "title_zh_tw": article.get("title_zh_tw"),
                "title_zh_cn": article.get("title_zh_cn"),
                "title_en": article.get("title_en"),
                "content_zh_tw": article.get("summary_zh_tw"),
                "content_zh_cn": article.get("summary_zh_cn"),
                "content_en": article.get("summary_en"),
                # 檢測原始語言（基於哪個翻譯字段為空來推斷）
                "original_language": _detect_original_language(article)
            }
            
            cleaned_articles.append(cleaned_article)
        
        return {
            "articles": cleaned_articles,
            "language": language,
            "total": len(cleaned_articles)
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _detect_original_language(article: Dict[str, Any]) -> str:
    """
    根據翻譯字段的存在情況推斷原始語言
    
    Args:
        article: 文章數據字典
        
    Returns:
        推斷的原始語言代碼
    """
    # 如果某個語言的翻譯為空，可能就是原始語言
    if not article.get("title_zh_tw"):
        return "zh-tw"
    elif not article.get("title_zh_cn"):
        return "zh-cn"
    elif not article.get("title_en"):
        return "en"
    else:
        # 如果都有翻譯，默認返回未知
        return "unknown"


@app.post("/api/refresh")
async def refresh() -> Dict[str, Any]:
    """
    Manually trigger fetching all RSS feeds with immediate translation.

    Returns:
        JSON payload with how many new articles were inserted.
    """
    result = await fetch_and_store_news()
    return {"detail": "Refresh complete (with translation)", **result}


@app.post("/api/translate/{article_url:path}")
async def translate_article(article_url: str, request: Request) -> Dict[str, Any]:
    """
    Manually trigger translation for a specific article.
    新流程：從資料庫提取原始資料 → 檢查是否已翻譯 → OpenAI翻譯 → 更新回資料庫
    
    安全改進：
    - 檢查文章是否已經翻譯完成
    - 檢查最近翻譯記錄，防止頻繁重複翻譯
    - 記錄翻譯請求以供監控

    Args:
        article_url: The URL of the article to translate.

    Returns:
        JSON payload with translation status.
    """
    try:
        # 檢查 IP 速率限制
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {TRANSLATION_RATE_LIMIT} translation requests per hour per IP."
            )
        
        from .translation_service import get_translation_service
        from .db import fetch_articles, update_article_translation, get_translation_logs
        from datetime import datetime, timedelta
        
        # 從資料庫獲取文章原始資料
        articles = await fetch_articles(language="original")
        article = next((a for a in articles if a['link'] == article_url), None)
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # 檢查文章是否已經完全翻譯
        has_zh_tw = article.get('title_zh_tw') is not None
        has_zh_cn = article.get('title_zh_cn') is not None
        has_en = article.get('title_en') is not None
        
        if has_zh_tw and has_zh_cn and has_en:
            return {
                "detail": "Article already fully translated",
                "article_url": article_url,
                "status": "already_translated",
                "translations_available": ["zh_tw", "zh_cn", "en"]
            }
        
        # 檢查最近是否有翻譯記錄（防止頻繁重複翻譯）
        # 使用 SQLite 的 datetime 函數直接在資料庫層面過濾
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        recent_logs = await get_translation_logs(
            article_link=article_url,
            since=one_hour_ago,
            limit=5
        )
        
        # 檢查是否有最近的成功翻譯記錄
        recent_successful_translations = [
            log for log in recent_logs
            if log.get('success')
        ]
        
        if recent_successful_translations:
            return {
                "detail": "Article was recently translated, please wait before retrying",
                "article_url": article_url,
                "status": "rate_limited",
                "retry_after": "1 hour",
                "last_translation": recent_successful_translations[0].get('created_at'),
                "recent_translations_count": len(recent_successful_translations)
            }
        
        # 使用翻譯服務翻譯原始內容
        service = get_translation_service()
        translation_result = await service.translate_with_auto_detection(
            article['original_title'],
            article['original_summary'] or ""
        )
        
        if translation_result.get('translation_status') != 'completed':
            raise HTTPException(status_code=500, detail="Translation failed")
        
        # 更新資料庫中的各語言翻譯（只更新缺失的翻譯）
        success_count = 0
        total_updates = 0
        updated_languages = []
        
        # 更新繁體中文翻譯（如果尚未翻譯）
        if not has_zh_tw and translation_result.get('title_zh_tw'):
            total_updates += 1
            success = await update_article_translation(
                article_link=article_url,
                target_language="zh_tw",
                title=translation_result.get('title_zh_tw'),
                summary=translation_result.get('content_zh_tw'),
                translation_service="openai",
                success=True
            )
            if success:
                success_count += 1
                updated_languages.append("zh_tw")
        
        # 更新簡體中文翻譯（如果尚未翻譯）
        if not has_zh_cn and translation_result.get('title_zh_cn'):
            total_updates += 1
            success = await update_article_translation(
                article_link=article_url,
                target_language="zh_cn",
                title=translation_result.get('title_zh_cn'),
                summary=translation_result.get('content_zh_cn'),
                translation_service="openai",
                success=True
            )
            if success:
                success_count += 1
                updated_languages.append("zh_cn")
        
        # 更新英文翻譯（如果尚未翻譯）
        if not has_en and translation_result.get('title_en'):
            total_updates += 1
            success = await update_article_translation(
                article_link=article_url,
                target_language="en",
                title=translation_result.get('title_en'),
                summary=translation_result.get('content_en'),
                translation_service="openai",
                success=True
            )
            if success:
                success_count += 1
                updated_languages.append("en")
        
        if success_count == 0:
            return {
                "detail": "No new translations needed",
                "article_url": article_url,
                "status": "no_updates_needed",
                "existing_translations": [
                    lang for lang, exists in [("zh_tw", has_zh_tw), ("zh_cn", has_zh_cn), ("en", has_en)]
                    if exists
                ]
            }
        
        return {
            "detail": "Translation complete",
            "article_url": article_url,
            "status": "success",
            "original_language": translation_result.get('original_language'),
            "translations_updated": success_count,
            "updated_languages": updated_languages,
            "total_translations_attempted": total_updates
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/refresh-fast")
async def refresh_fast() -> Dict[str, Any]:
    """
    快速刷新RSS feeds，跳過翻譯處理
    
    Returns:
        JSON payload with how many new articles were inserted.
    """
    result = await refresh_feeds_fast()
    return {"detail": "Fast refresh complete", **result}


@app.post("/api/batch-translate")
async def batch_translate(limit: Optional[int] = Query(None, gt=0)) -> Dict[str, Any]:
    """
    翻譯現有的未翻譯文章（向後相容性端點）
    注意：在新的即時翻譯流程中，此端點主要用於處理舊資料
    
    Query Args:
        limit: 限制處理的文章數量
        
    Returns:
        翻譯處理結果
    """
    try:
        result = await translate_missing_articles(limit)
        return {"detail": "Missing articles translation complete", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/translation-stats")
async def get_translation_statistics() -> Dict[str, Any]:
    """
    獲取翻譯統計信息
    
    Returns:
        翻譯統計數據
    """
    try:
        stats = await get_translation_stats()
        return {"detail": "Translation statistics", **stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/cleanup-duplicates")
async def cleanup_duplicates() -> Dict[str, Any]:
    """
    清理重複的文章（基於URL唯一性）
    
    Returns:
        清理結果統計
    """
    try:
        result = await ensure_url_uniqueness()
        return {"detail": "Duplicate cleanup complete", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """
    健康檢查端點
    
    Returns:
        系統狀態信息
    """
    try:
        # 檢查數據庫連接
        stats = await get_translation_stats()
        
        # 檢查翻譯服務
        from .translation_service import get_translation_service
        service = get_translation_service()
        
        # 檢查調度器狀態
        scheduler = get_scheduler()
        scheduler_status = scheduler.get_status()
        
        return {
            "status": "healthy",
            "database": "connected",
            "translation_service": "available",
            "scheduler": "running" if scheduler_status["is_running"] else "stopped",
            "total_articles": str(stats["total_articles"])
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(exc)}") from exc


@app.get("/api/scheduler/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """
    獲取調度器狀態
    
    Returns:
        調度器詳細狀態信息
    """
    try:
        scheduler = get_scheduler()
        return scheduler.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scheduler/start")
async def start_scheduler_endpoint() -> Dict[str, str]:
    """
    啟動調度器
    
    Returns:
        操作結果
    """
    try:
        scheduler = get_scheduler()
        scheduler.start()
        return {"detail": "調度器已啟動"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scheduler/stop")
async def stop_scheduler_endpoint() -> Dict[str, str]:
    """
    停止調度器
    
    Returns:
        操作結果
    """
    try:
        scheduler = get_scheduler()
        scheduler.stop()
        return {"detail": "調度器已停止"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scheduler/trigger-fetch")
async def trigger_fetch_now() -> Dict[str, Any]:
    """
    立即觸發新聞抓取
    
    Returns:
        抓取結果
    """
    try:
        scheduler = get_scheduler()
        result = await scheduler.trigger_fetch_now()
        return {"detail": "手動抓取完成", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scheduler/toggle-fetch")
async def toggle_fetch(enabled: bool = Query(...)) -> Dict[str, str]:
    """
    啟用/停用自動抓取
    
    Query Args:
        enabled: 是否啟用自動抓取
        
    Returns:
        操作結果
    """
    try:
        scheduler = get_scheduler()
        scheduler.enable_fetch(enabled)
        return {"detail": f"自動抓取已{'啟用' if enabled else '停用'}"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scheduler/toggle-translation")
async def toggle_translation(enabled: bool = Query(...)) -> Dict[str, str]:
    """
    啟用/停用自動翻譯
    
    Query Args:
        enabled: 是否啟用自動翻譯
        
    Returns:
        操作結果
    """
    try:
        scheduler = get_scheduler()
        scheduler.enable_translation(enabled)
        return {"detail": f"自動翻譯已{'啟用' if enabled else '停用'}"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/translation-monitoring")
async def get_translation_monitoring() -> Dict[str, Any]:
    """
    獲取翻譯請求監控資訊
    
    Returns:
        翻譯請求統計和速率限制狀態
    """
    try:
        from .db import get_translation_logs
        
        current_time = time.time()
        
        # 清理過期的速率限制記錄
        active_ips = {}
        for ip, timestamps in translation_requests.items():
            active_timestamps = [
                ts for ts in timestamps
                if current_time - ts < RATE_LIMIT_WINDOW
            ]
            if active_timestamps:
                active_ips[ip] = {
                    "requests_count": len(active_timestamps),
                    "remaining_requests": max(0, TRANSLATION_RATE_LIMIT - len(active_timestamps)),
                    "oldest_request": min(active_timestamps),
                    "newest_request": max(active_timestamps)
                }
        
        # 獲取最近的翻譯日誌
        recent_logs = await get_translation_logs(limit=50)
        
        # 統計成功/失敗的翻譯
        successful_translations = sum(1 for log in recent_logs if log.get('success'))
        failed_translations = len(recent_logs) - successful_translations
        
        return {
            "rate_limit_config": {
                "max_requests_per_hour": TRANSLATION_RATE_LIMIT,
                "window_seconds": RATE_LIMIT_WINDOW
            },
            "active_ips": active_ips,
            "recent_translation_stats": {
                "total_recent_logs": len(recent_logs),
                "successful_translations": successful_translations,
                "failed_translations": failed_translations,
                "success_rate": round(successful_translations / len(recent_logs) * 100, 2) if recent_logs else 0
            },
            "system_status": {
                "timestamp": current_time,
                "active_rate_limited_ips": len(active_ips)
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/reset-rate-limits")
async def reset_rate_limits() -> Dict[str, str]:
    """
    重置所有 IP 的速率限制（管理員功能）
    
    Returns:
        操作結果
    """
    try:
        global translation_requests
        cleared_ips = len(translation_requests)
        translation_requests.clear()
        
        return {
            "detail": f"已重置 {cleared_ips} 個 IP 的速率限制記錄",
            "cleared_ips": cleared_ips
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc