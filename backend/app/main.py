from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import fetch_articles, init_db, get_translation_stats, ensure_url_uniqueness
from .rss_fetcher import fetch_and_store_news, translate_missing_articles, refresh_feeds_fast
from .scheduler import get_scheduler, start_scheduler, stop_scheduler

# 載入環境變數
load_dotenv()

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


# 移除了手動翻譯特定文章的端點以防止濫用
# 翻譯功能現在只能通過以下方式觸發：
# 1. 自動排程翻譯（每10分鐘）
# 2. 手動刷新並翻譯 (/api/refresh)
# 3. 批次翻譯未翻譯文章 (/api/batch-translate)

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


# 移除了監控和速率限制相關端點，因為已經移除了主要的安全風險端點