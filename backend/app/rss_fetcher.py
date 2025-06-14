from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional

import feedparser
from dotenv import load_dotenv

from .db import insert_article, article_exists
from .translation_service import get_translation_service

# RSS feed sources are defined in a separate module for easier maintenance.
from .feeds import FEEDS

# 載入環境變數
load_dotenv()

logger = logging.getLogger(__name__)


def clean_html_content(content: str) -> str:
    """
    清理HTML內容：只保留第一個<p>段落的內容，並移除<p>標籤
    
    Args:
        content: 原始HTML內容
        
    Returns:
        清理後的純文字內容
    """
    if not content:
        return content
    
    # 使用正則表達式找到第一個<p>標籤的內容
    p_pattern = r'<p[^>]*>(.*?)</p>'
    matches = re.findall(p_pattern, content, re.DOTALL | re.IGNORECASE)
    
    if matches:
        # 取第一個<p>段落的內容
        first_p_content = matches[0]
        # 移除內部的HTML標籤（如<a>標籤等）
        clean_content = re.sub(r'<[^>]+>', '', first_p_content)
        # 清理多餘的空白字符
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        return clean_content
    
    # 如果沒有找到<p>標籤，返回原始內容（移除所有HTML標籤）
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    return clean_content


async def _process_entry(entry: Dict[str, str], feed_source: str, skip_translation: bool = False) -> bool:
    """
    Insert a single RSS entry into the database with immediate translation.
    新流程：抓取RSS → 即時翻譯 → 儲存完整資料到資料庫

    Args:
        entry: An RSS entry parsed by feedparser.
        feed_source: Human-readable feed name or URL for tracking origin.
        skip_translation: If True, skip translation and only store raw content.

    Returns:
        True if the article was newly inserted, otherwise False.
    """
    title: str = entry.get("title", "").strip()
    link: str = entry.get("link", "").strip()
    raw_summary: str = entry.get("summary", entry.get("description", "")).strip()
    # 清理HTML內容
    summary: str = clean_html_content(raw_summary)
    published: str = entry.get("published", "")
    
    if not link:
        # Skip entries without a unique link
        logger.debug(f"Skipping entry without link: {title}")
        return False
    
    # 檢查URL是否已存在
    if await article_exists(link):
        logger.debug(f"Article already exists, skipping: {link}")
        return False
    
    logger.debug(f"Processing new article: {title}")
    
    # 準備翻譯內容
    title_zh_tw = None
    summary_zh_tw = None
    title_zh_cn = None
    summary_zh_cn = None
    title_en = None
    summary_en = None
    
    # 如果不跳過翻譯，進行即時翻譯
    if not skip_translation:
        try:
            logger.info(f"開始翻譯文章: {title[:50]}...")
            service = get_translation_service()
            translation_result = await service.translate_with_auto_detection(title, summary)
            
            if translation_result.get('translation_status') == 'completed':
                title_zh_tw = translation_result.get('title_zh_tw')
                summary_zh_tw = translation_result.get('content_zh_tw')
                title_zh_cn = translation_result.get('title_zh_cn')
                summary_zh_cn = translation_result.get('content_zh_cn')
                title_en = translation_result.get('title_en')
                summary_en = translation_result.get('content_en')
                logger.info(f"翻譯成功: {title[:50]}")
            else:
                logger.warning(f"翻譯失敗，僅儲存原始資料: {title[:50]}")
                
        except Exception as e:
            logger.error(f"翻譯過程發生錯誤: {e}，僅儲存原始資料")
    
    # 儲存文章（包含原始資料和翻譯）
    success = await insert_article(
        link=link,
        original_title=title,
        original_summary=summary,
        published=published,
        feed_source=feed_source,
        title_zh_tw=title_zh_tw,
        summary_zh_tw=summary_zh_tw,
        title_zh_cn=title_zh_cn,
        summary_zh_cn=summary_zh_cn,
        title_en=title_en,
        summary_en=summary_en
    )
    
    if not success:
        logger.error(f"Failed to insert article: {title}")
        return False
    
    logger.debug(f"Article successfully stored with translations: {title}")
    return True


async def _fetch_single_feed(url: str, skip_translation: bool = False) -> int:
    """
    Fetch and process a single RSS feed with immediate translation.

    Args:
        url: The RSS feed URL.
        skip_translation: If True, skip translation for faster processing.

    Returns:
        The number of new articles inserted from this feed.
    """
    try:
        feed_data = await asyncio.to_thread(feedparser.parse, url)
        feed_title: str = feed_data.feed.get("title", url)
        
        # 調整並發控制：如果需要翻譯，降低並發數以避免API速率限制
        if skip_translation:
            semaphore = asyncio.Semaphore(5)  # 不翻譯時可以更高並發
        else:
            semaphore = asyncio.Semaphore(2)  # 翻譯時降低並發數
        
        async def process_with_semaphore(entry):
            async with semaphore:
                return await _process_entry(entry, feed_title, skip_translation)
        
        tasks = [process_with_semaphore(entry) for entry in feed_data.entries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 計算成功插入的文章數量
        successful_inserts = 0
        for result in results:
            if isinstance(result, bool) and result:
                successful_inserts += 1
            elif isinstance(result, Exception):
                logger.error(f"Error processing entry from {url}: {result}")
        
        return successful_inserts
        
    except Exception as e:
        logger.error(f"Failed to fetch feed {url}: {e}")
        return 0


async def fetch_all_feeds(skip_translation: bool = False) -> Dict[str, int]:
    """
    Fetch all feeds defined in FEEDS with immediate translation.

    Args:
        skip_translation: If True, skip translation and only store raw content.
                         If False, perform immediate translation for each article.

    Returns:
        Dictionary with the total number of new articles inserted.
    """
    total_new = 0
    failed_feeds = []
    
    for url in FEEDS:
        try:
            new_count = await _fetch_single_feed(url, skip_translation)
            total_new += new_count
            logger.info(f"Fetched {new_count} new articles from {url}")
        except Exception as e:
            logger.error(f"Failed to process feed {url}: {e}")
            failed_feeds.append(url)
    
    result = {"new_articles": total_new}
    if failed_feeds:
        result["failed_feeds"] = failed_feeds
    
    return result


async def translate_missing_articles(limit: Optional[int] = None) -> Dict[str, int]:
    """
    翻譯現有未翻譯的文章（向後相容性函數）
    注意：在新的即時翻譯流程中，此函數主要用於處理舊資料
    
    Args:
        limit: 限制處理的文章數量
        
    Returns:
        翻譯結果統計
    """
    try:
        from .db import fetch_articles_for_translation, update_article_translation
        
        # 獲取需要翻譯的文章
        articles_to_translate = []
        
        # 按優先級獲取需要翻譯的文章
        for lang in ["zh_tw", "zh_cn", "en"]:
            if limit is None or len(articles_to_translate) < limit:
                remaining_limit = None if limit is None else limit - len(articles_to_translate)
                articles = await fetch_articles_for_translation(lang, remaining_limit)
                articles_to_translate.extend([(article, lang) for article in articles])
        
        if not articles_to_translate:
            return {"message": "No articles need translation", "processed": 0}
        
        logger.info(f"開始翻譯 {len(articles_to_translate)} 篇未翻譯的文章")
        
        service = get_translation_service()
        successful_updates = 0
        failed_updates = 0
        
        for article, target_language in articles_to_translate:
            try:
                logger.info(f"翻譯文章到 {target_language}: {article['original_title'][:50]}...")
                
                translation_result = await service.translate_with_auto_detection(
                    article['original_title'],
                    article['original_summary'] or ""
                )
                
                if translation_result.get('translation_status') == 'completed':
                    # 根據目標語言選擇翻譯結果
                    if target_language == "zh_tw":
                        title = translation_result.get('title_zh_tw')
                        summary = translation_result.get('content_zh_tw')
                    elif target_language == "zh_cn":
                        title = translation_result.get('title_zh_cn')
                        summary = translation_result.get('content_zh_cn')
                    else:  # en
                        title = translation_result.get('title_en')
                        summary = translation_result.get('content_en')
                    
                    success = await update_article_translation(
                        article_link=article['link'],
                        target_language=target_language,
                        title=title,
                        summary=summary,
                        translation_service="openai",
                        success=True
                    )
                    
                    if success:
                        successful_updates += 1
                        logger.info(f"成功翻譯文章: {article['original_title'][:50]}")
                    else:
                        failed_updates += 1
                        logger.error(f"更新資料庫失敗: {article['link']}")
                else:
                    failed_updates += 1
                    logger.error(f"翻譯失敗: {article['original_title'][:50]}")
                
                # API速率限制
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"翻譯文章時發生錯誤 {article['link']}: {e}")
                failed_updates += 1
        
        return {
            "processed": len(articles_to_translate),
            "successful": successful_updates,
            "failed": failed_updates
        }
        
    except Exception as e:
        logger.error(f"批次翻譯失敗: {e}")
        return {"error": str(e), "processed": 0}


async def fetch_and_store_news() -> Dict[str, int]:
    """
    抓取並儲存新聞（包含即時翻譯）
    
    Returns:
        抓取結果統計
    """
    return await fetch_all_feeds(skip_translation=False)


async def refresh_feeds_fast() -> Dict[str, int]:
    """
    快速刷新RSS feeds，跳過翻譯
    
    Returns:
        刷新結果統計
    """
    return await fetch_all_feeds(skip_translation=True)