from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime
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

# 全局鎖，防止重複翻譯同一篇文章
_translation_locks: Dict[str, asyncio.Lock] = {}
_translation_locks_lock = asyncio.Lock()

async def _get_translation_lock(article_url: str) -> asyncio.Lock:
    """獲取特定文章的翻譯鎖"""
    async with _translation_locks_lock:
        if article_url not in _translation_locks:
            _translation_locks[article_url] = asyncio.Lock()
        return _translation_locks[article_url]

async def _cleanup_translation_lock(article_url: str):
    """清理已完成的翻譯鎖"""
    async with _translation_locks_lock:
        if article_url in _translation_locks:
            del _translation_locks[article_url]


def normalize_published_time(entry: Dict) -> str:
    """
    標準化RSS條目的發布時間為RFC 2822格式
    
    Args:
        entry: feedparser解析的RSS條目
        
    Returns:
        標準化的RFC 2822時間字符串，如果無法解析則返回空字符串
    """
    try:
        # 優先使用feedparser解析的時間結構
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            # 將time.struct_time轉換為datetime，然後格式化為RFC 2822
            dt = datetime(*entry.published_parsed[:6])
            # RFC 2822格式: "Day, DD Mon YYYY HH:MM:SS +0000"
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # 如果沒有parsed time，嘗試解析字符串格式的時間
        published_str = entry.get('published', '')
        if published_str:
            # 嘗試解析常見的時間格式
            try:
                # 如果已經是RFC 2822格式，直接返回（可能需要標準化時區）
                if re.match(r'^[A-Za-z]{3}, \d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}', published_str):
                    # 確保時區格式統一為 +0000
                    if published_str.endswith(' +0000') or published_str.endswith(' GMT') or published_str.endswith(' UTC'):
                        return re.sub(r' (GMT|UTC)$', ' +0000', published_str)
                    elif '+' in published_str or '-' in published_str[-6:]:
                        # 保持原有時區格式
                        return published_str
                    else:
                        # 如果沒有時區信息，添加 +0000
                        return published_str + ' +0000'
                
                # 嘗試解析RFC 2822格式
                try:
                    parsed_time = time.strptime(published_str.replace(' GMT', ' +0000').replace(' UTC', ' +0000'), '%a, %d %b %Y %H:%M:%S %z')
                    dt = datetime(*parsed_time[:6])
                    return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
                except ValueError:
                    pass
                
                # 嘗試解析ISO 8601格式 (如: "2025-06-13T20:16:24-04:00")
                try:
                    # 處理不同的ISO 8601變體
                    iso_str = published_str
                    if 'T' in iso_str:
                        # 移除時區信息進行基本解析
                        time_part = iso_str.split('+')[0].split('Z')[0]
                        if time_part.count('-') > 2:  # 包含時區的情況
                            time_part = time_part.rsplit('-', 1)[0]
                        dt = datetime.fromisoformat(time_part)
                        return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
                except ValueError:
                    pass
                
                logger.warning(f"無法解析時間格式: {published_str}")
                return ''
                
            except Exception as parse_error:
                logger.warning(f"時間解析錯誤: {parse_error}, 原始時間: {published_str}")
                return ''
        
        return ''
        
    except Exception as e:
        logger.error(f"時間標準化錯誤: {e}")
        return ''


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
    新流程：抓取RSS → 檢查重複 → 即時翻譯 → 儲存完整資料到資料庫
    
    修復：添加全局鎖機制防止重複翻譯同一篇文章

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
    
    # 使用標準化的時間格式
    published: str = normalize_published_time(entry)
    
    # 如果標準化失敗，使用原始時間並記錄警告
    if not published:
        raw_published = entry.get("published", "")
        logger.warning(f"無法標準化時間，使用原始時間: {raw_published}")
        published = raw_published
    
    if not link:
        # Skip entries without a unique link
        logger.debug(f"Skipping entry without link: {title}")
        return False
    
    # 獲取該文章的專用鎖
    article_lock = await _get_translation_lock(link)
    
    async with article_lock:
        # 在鎖內再次檢查文章是否已存在
        if await article_exists(link):
            logger.debug(f"Article already exists (checked under lock), skipping: {link}")
            await _cleanup_translation_lock(link)
            return False
        
        logger.debug(f"Processing new article under lock: {title[:50]}...")
        
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
        
        # 翻譯完成後最終檢查，防止競態條件導致重複插入
        if await article_exists(link):
            logger.debug(f"Article was inserted by another process during translation, skipping: {link}")
            await _cleanup_translation_lock(link)
            return False
        
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
        
        # 清理鎖
        await _cleanup_translation_lock(link)
        
        if not success:
            # 插入失敗可能是因為文章已存在（資料庫層面的重複檢查）
            logger.debug(f"Article insertion failed (likely duplicate): {title}")
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
        
        logger.info(f"開始處理 RSS feed: {feed_title} ({len(feed_data.entries)} 篇文章)")
        
        # 進一步降低並發控制，確保翻譯過程的穩定性
        if skip_translation:
            semaphore = asyncio.Semaphore(2)  # 不翻譯時降低並發
        else:
            # 翻譯時完全序列化處理，配合全局鎖機制
            semaphore = asyncio.Semaphore(1)
        
        async def process_with_semaphore(entry):
            async with semaphore:
                try:
                    return await _process_entry(entry, feed_title, skip_translation)
                except Exception as e:
                    logger.error(f"處理文章時發生錯誤: {e}")
                    return False
        
        # 序列處理所有文章，避免同時處理相同文章
        successful_inserts = 0
        for entry in feed_data.entries:
            try:
                result = await process_with_semaphore(entry)
                if result:
                    successful_inserts += 1
                # 在翻譯模式下添加延遲，避免API速率限制
                if not skip_translation:
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error processing entry from {url}: {e}")
        
        logger.info(f"完成處理 RSS feed: {feed_title} (新增 {successful_inserts} 篇文章)")
        return successful_inserts
        
    except Exception as e:
        logger.error(f"Failed to fetch feed {url}: {e}")
        return 0


# 全局執行狀態控制
_fetch_in_progress = False
_fetch_lock = asyncio.Lock()

async def fetch_all_feeds(skip_translation: bool = False) -> Dict[str, int]:
    """
    Fetch all feeds defined in FEEDS with immediate translation.
    添加全局執行狀態控制，防止重複執行

    Args:
        skip_translation: If True, skip translation and only store raw content.
                         If False, perform immediate translation for each article.

    Returns:
        Dictionary with the total number of new articles inserted.
    """
    global _fetch_in_progress
    
    async with _fetch_lock:
        if _fetch_in_progress:
            logger.warning("RSS 抓取任務已在執行中，跳過此次請求")
            return {"error": "RSS 抓取任務已在執行中", "new_articles": 0}
        
        _fetch_in_progress = True
    
    try:
        logger.info(f"開始抓取所有 RSS feeds (共 {len(FEEDS)} 個源)")
        total_new = 0
        failed_feeds = []
        
        # 序列處理所有 feeds，避免同時處理造成重複
        for i, url in enumerate(FEEDS, 1):
            try:
                logger.info(f"處理第 {i}/{len(FEEDS)} 個 RSS 源: {url}")
                new_count = await _fetch_single_feed(url, skip_translation)
                total_new += new_count
                logger.info(f"完成第 {i}/{len(FEEDS)} 個源，新增 {new_count} 篇文章")
                
                # 在處理不同 feeds 之間添加短暫延遲
                if i < len(FEEDS):
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Failed to process feed {url}: {e}")
                failed_feeds.append(url)
        
        result = {"new_articles": total_new}
        if failed_feeds:
            result["failed_feeds"] = failed_feeds
        
        logger.info(f"完成所有 RSS feeds 抓取，總共新增 {total_new} 篇文章")
        return result
        
    finally:
        async with _fetch_lock:
            _fetch_in_progress = False


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