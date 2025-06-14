from __future__ import annotations

import aiosqlite
from typing import Any, Dict, List, Optional
from datetime import datetime
import os

# 獲取當前檔案的目錄路徑，確保資料庫檔案路徑正確
DB_FILE = os.path.join(os.path.dirname(__file__), "ai_news.db")


async def _migrate_published_column(db: aiosqlite.Connection) -> None:
    """
    遷移published字段從TEXT類型到DATETIME類型，並標準化現有時間數據為RFC 2822格式
    """
    try:
        # 檢查表是否存在
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
        ) as cursor:
            table_exists = await cursor.fetchone()
        
        if not table_exists:
            return  # 表不存在，無需遷移
        
        # 檢查published字段的類型
        async with db.execute("PRAGMA table_info(articles)") as cursor:
            columns = await cursor.fetchall()
            published_column = None
            for col in columns:
                if col[1] == 'published':  # col[1] is column name
                    published_column = col
                    break
        
        if not published_column:
            return  # published字段不存在
        
        # 如果published字段已經是DATETIME類型，檢查是否需要標準化數據
        if 'DATETIME' in published_column[2].upper():
            # 檢查是否有非標準格式的時間數據需要更新
            async with db.execute(
                "SELECT COUNT(*) FROM articles WHERE published LIKE '%,%' OR published LIKE '%+%'"
            ) as cursor:
                non_standard_count = (await cursor.fetchone())[0]
            
            if non_standard_count > 0:
                print(f"發現 {non_standard_count} 條需要標準化的時間記錄，開始更新...")
                await _standardize_existing_times(db)
            return
        
        print("開始遷移published字段類型從TEXT到DATETIME...")
        
        # 創建新表結構
        await db.execute(
            """
            CREATE TABLE articles_new (
                link TEXT PRIMARY KEY,
                original_title TEXT NOT NULL,
                original_summary TEXT,
                published DATETIME,
                feed_source TEXT,
                title_zh_tw TEXT,
                summary_zh_tw TEXT,
                title_zh_cn TEXT,
                summary_zh_cn TEXT,
                title_en TEXT,
                summary_en TEXT
            )
            """
        )
        
        # 遷移數據並標準化時間格式
        await _migrate_and_standardize_data(db)
        
        # 刪除舊表並重命名新表
        await db.execute("DROP TABLE articles")
        await db.execute("ALTER TABLE articles_new RENAME TO articles")
        
        print("published字段類型遷移完成")
        
    except Exception as e:
        print(f"遷移過程中發生錯誤: {e}")
        # 如果遷移失敗，嘗試清理
        try:
            await db.execute("DROP TABLE IF EXISTS articles_new")
        except:
            pass


async def _migrate_and_standardize_data(db: aiosqlite.Connection) -> None:
    """
    遷移數據並標準化時間格式
    """
    import time
    from datetime import datetime
    
    async with db.execute("SELECT * FROM articles") as cursor:
        rows = await cursor.fetchall()
    
    migrated_count = 0
    failed_count = 0
    
    for row in rows:
        try:
            # 解析舊的時間格式並標準化
            old_published = row[3]  # published字段在第4列 (index 3)
            standardized_time = _standardize_time_string(old_published)
            
            # 插入到新表
            await db.execute(
                """
                INSERT INTO articles_new (
                    link, original_title, original_summary, published, feed_source,
                    title_zh_tw, summary_zh_tw, title_zh_cn, summary_zh_cn,
                    title_en, summary_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row[0], row[1], row[2], standardized_time, row[4],
                    row[5], row[6], row[7], row[8], row[9], row[10]
                )
            )
            migrated_count += 1
            
        except Exception as e:
            print(f"遷移記錄失敗 {row[0]}: {e}")
            failed_count += 1
    
    print(f"遷移完成: {migrated_count} 成功, {failed_count} 失敗")


async def _standardize_existing_times(db: aiosqlite.Connection) -> None:
    """
    標準化現有數據庫中的時間格式
    """
    async with db.execute("SELECT link, published FROM articles WHERE published IS NOT NULL") as cursor:
        rows = await cursor.fetchall()
    
    updated_count = 0
    for link, old_published in rows:
        try:
            standardized_time = _standardize_time_string(old_published)
            if standardized_time != old_published:
                await db.execute(
                    "UPDATE articles SET published = ? WHERE link = ?",
                    (standardized_time, link)
                )
                updated_count += 1
        except Exception as e:
            print(f"標準化時間失敗 {link}: {e}")
    
    print(f"標準化完成: {updated_count} 條記錄已更新")


def _standardize_time_string(time_str: str) -> str:
    """
    標準化時間字符串為RFC 2822格式
    """
    if not time_str:
        return ''
    
    try:
        import time as time_module
        import re
        from datetime import datetime
        
        # 如果已經是RFC 2822格式，進行標準化處理
        if re.match(r'^[A-Za-z]{3}, \d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}', time_str):
            # 確保時區格式統一
            if time_str.endswith(' +0000') or time_str.endswith(' GMT') or time_str.endswith(' UTC'):
                return re.sub(r' (GMT|UTC)$', ' +0000', time_str)
            elif '+' in time_str or '-' in time_str[-6:]:
                # 保持原有時區格式
                return time_str
            else:
                # 如果沒有時區信息，添加 +0000
                return time_str + ' +0000'
        
        # 嘗試解析RFC 2822格式並標準化
        try:
            parsed_time = time_module.strptime(time_str.replace(' GMT', ' +0000').replace(' UTC', ' +0000'), '%a, %d %b %Y %H:%M:%S %z')
            dt = datetime(*parsed_time[:6])
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
        except ValueError:
            pass
        
        # 嘗試解析ISO 8601格式並轉換為RFC 2822
        try:
            if 'T' in time_str:
                # 處理不同的ISO 8601變體
                time_part = time_str.split('+')[0].split('Z')[0]
                if time_part.count('-') > 2:  # 包含時區的情況
                    time_part = time_part.rsplit('-', 1)[0]
                dt = datetime.fromisoformat(time_part)
                return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
        except ValueError:
            pass
        
        # 如果都無法解析，返回原始字符串
        return time_str
        
    except Exception:
        return time_str


async def init_db() -> None:
    """
    初始化 SQLite 資料庫並創建精簡的多語言文章表結構
    
    精簡後的資料庫結構特點：
    - 使用 URL (link) 作為主鍵
    - 只保留必要的原始內容和翻譯欄位
    - 支援多語言翻譯（繁體中文、簡體中文、英文）
    - 使用DATETIME類型的published字段以提升排序性能
    - 簡化索引結構
    """
    async with aiosqlite.connect(DB_FILE) as db:
        # 檢查是否需要遷移現有表結構
        await _migrate_published_column(db)
        
        # 創建精簡的文章表
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                -- 主鍵
                link TEXT PRIMARY KEY,
                
                -- 原始內容
                original_title TEXT NOT NULL,
                original_summary TEXT,
                
                -- RSS 來源資訊 (使用DATETIME類型以提升排序性能)
                published DATETIME,
                feed_source TEXT,
                
                -- 翻譯內容
                title_zh_tw TEXT,
                summary_zh_tw TEXT,
                title_zh_cn TEXT,
                summary_zh_cn TEXT,
                title_en TEXT,
                summary_en TEXT
            )
            """
        )
        
        # 創建基本索引
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_feed_source ON articles(feed_source)"
        )
        
        # 創建翻譯日誌表（用於追蹤翻譯歷史）
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_link TEXT NOT NULL,
                target_language TEXT NOT NULL,
                translation_type TEXT NOT NULL, -- 'title', 'summary', 'content'
                original_text TEXT,
                translated_text TEXT,
                translation_service TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                FOREIGN KEY (article_link) REFERENCES articles (link) ON DELETE CASCADE
            )
            """
        )
        
        # 創建翻譯日誌索引
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_translation_logs_article ON translation_logs(article_link)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_translation_logs_language ON translation_logs(target_language)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_translation_logs_created_at ON translation_logs(created_at DESC)"
        )
        
        await db.commit()


async def insert_article(
    link: str,
    original_title: str,
    original_summary: str = "",
    published: str = "",
    feed_source: str = "",
    # 可選的翻譯內容
    title_zh_tw: Optional[str] = None,
    summary_zh_tw: Optional[str] = None,
    title_zh_cn: Optional[str] = None,
    summary_zh_cn: Optional[str] = None,
    title_en: Optional[str] = None,
    summary_en: Optional[str] = None,
) -> bool:
    """
    插入新文章到資料庫
    
    Args:
        link: 文章URL（主鍵）
        original_title: 原始標題
        original_summary: 原始摘要
        published: 發布時間
        feed_source: RSS來源
        其他翻譯相關參數: 可選的翻譯內容
        
    Returns:
        True 如果文章成功插入，False 如果文章已存在
    """
    if not link or not link.strip():
        return False
    
    if not original_title or not original_title.strip():
        return False
    
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute(
                """
                INSERT INTO articles (
                    link, original_title, original_summary, published, feed_source,
                    title_zh_tw, summary_zh_tw, title_zh_cn, summary_zh_cn,
                    title_en, summary_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link, original_title, original_summary, published, feed_source,
                    title_zh_tw, summary_zh_tw, title_zh_cn, summary_zh_cn,
                    title_en, summary_en
                )
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # 文章已存在
            return False


async def article_exists(link: str) -> bool:
    """
    檢查文章URL是否已存在於資料庫中
    
    Args:
        link: 文章URL
        
    Returns:
        True 如果文章存在，False 否則
    """
    if not link or not link.strip():
        return False
        
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT 1 FROM articles WHERE link = ? LIMIT 1", (link,)) as cursor:
            result = await cursor.fetchone()
            return result is not None


async def fetch_articles(
    limit: Optional[int] = None,
    language: str = "zh_tw",
    include_untranslated: bool = True
) -> List[Dict[str, Any]]:
    """
    從資料庫獲取文章，按發布日期排序
    
    Args:
        limit: 可選的最大文章數量限制
        language: 目標語言 ('zh_tw', 'zh_cn', 'en', 'original')
        include_untranslated: 是否包含未翻譯的文章
        
    Returns:
        文章列表（字典格式）
    """
    # 根據語言選擇相應的欄位
    if language == "zh_tw":
        title_field = "COALESCE(title_zh_tw, original_title)"
        summary_field = "COALESCE(summary_zh_tw, original_summary)"
    elif language == "zh_cn":
        title_field = "COALESCE(title_zh_cn, original_title)"
        summary_field = "COALESCE(summary_zh_cn, original_summary)"
    elif language == "en":
        title_field = "COALESCE(title_en, original_title)"
        summary_field = "COALESCE(summary_en, original_summary)"
    else:  # original
        title_field = "original_title"
        summary_field = "original_summary"
    
    where_clause = ""
    if not include_untranslated and language != "original":
        if language == "zh_tw":
            where_clause = "WHERE title_zh_tw IS NOT NULL"
        elif language == "zh_cn":
            where_clause = "WHERE title_zh_cn IS NOT NULL"
        elif language == "en":
            where_clause = "WHERE title_en IS NOT NULL"
    
    query = f"""
        SELECT
            link,
            {title_field} as title,
            {summary_field} as summary,
            original_title,
            original_summary,
            published,
            feed_source,
            title_zh_tw,
            summary_zh_tw,
            title_zh_cn,
            summary_zh_cn,
            title_en,
            summary_en
        FROM articles
        {where_clause}
    """

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            articles = [dict(row) for row in rows]
            
            # 在 Python 中進行排序，確保正確處理時間格式
            def parse_published_time(published_str):
                if not published_str:
                    return 0
                try:
                    from datetime import datetime
                    import time
                    
                    # 嘗試解析 RFC 2822 格式
                    if ',' in published_str:
                        parsed_time = time.strptime(published_str.replace(' GMT', ' +0000').replace(' UTC', ' +0000'), '%a, %d %b %Y %H:%M:%S %z')
                        return time.mktime(parsed_time)
                    
                    # 嘗試解析 ISO 格式
                    if 'T' in published_str:
                        dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                        return dt.timestamp()
                    
                    # 嘗試直接解析
                    dt = datetime.fromisoformat(published_str)
                    return dt.timestamp()
                    
                except:
                    return 0
            
            # 按發布時間降序排序（最新的在前）
            articles.sort(key=lambda x: parse_published_time(x.get('published', '')), reverse=True)
            
            # 應用 limit
            if limit is not None:
                articles = articles[:limit]
                
            return articles


async def fetch_articles_for_translation(
    target_language: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    獲取需要翻譯的文章
    
    Args:
        target_language: 目標語言 ('zh_tw', 'zh_cn', 'en')
        limit: 限制返回的文章數量
        
    Returns:
        需要翻譯的文章列表
    """
    # 根據目標語言構建查詢條件
    if target_language == "zh_tw":
        condition = "title_zh_tw IS NULL"
    elif target_language == "zh_cn":
        condition = "title_zh_cn IS NULL"
    elif target_language == "en":
        condition = "title_en IS NULL"
    else:
        raise ValueError(f"不支援的目標語言: {target_language}")
    
    query = f"""
        SELECT
            link, original_title, original_summary, published, feed_source
        FROM articles
        WHERE {condition}
        ORDER BY published DESC
    """
    
    params: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_article_translation(
    article_link: str,
    target_language: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    translation_service: str = "unknown",
    success: bool = True,
    error_message: Optional[str] = None
) -> bool:
    """
    更新文章的翻譯內容
    
    Args:
        article_link: 文章URL（主鍵）
        target_language: 目標語言 ('zh_tw', 'zh_cn', 'en')
        title: 翻譯後的標題
        summary: 翻譯後的摘要
        translation_service: 翻譯服務名稱
        success: 翻譯是否成功
        error_message: 錯誤訊息（如果翻譯失敗）
        
    Returns:
        更新是否成功
    """
    if not article_link or not article_link.strip():
        return False
    
    if target_language not in ["zh_tw", "zh_cn", "en"]:
        return False
    
    async with aiosqlite.connect(DB_FILE) as db:
        # 更新文章翻譯
        if success and title:
            # 根據目標語言更新相應欄位
            if target_language == "zh_tw":
                update_fields = "title_zh_tw = ?, summary_zh_tw = ?"
                params = (title, summary, article_link)
            elif target_language == "zh_cn":
                update_fields = "title_zh_cn = ?, summary_zh_cn = ?"
                params = (title, summary, article_link)
            else:  # en
                update_fields = "title_en = ?, summary_en = ?"
                params = (title, summary, article_link)
            
            await db.execute(
                f"""
                UPDATE articles SET {update_fields}
                WHERE link = ?
                """,
                params
            )
        
        # 記錄翻譯日誌
        if title:
            await db.execute(
                """
                INSERT INTO translation_logs (
                    article_link, target_language, translation_type,
                    translated_text, translation_service, success, error_message
                )
                VALUES (?, ?, 'title', ?, ?, ?, ?)
                """,
                (article_link, target_language, title, translation_service, success, error_message)
            )
        
        if summary:
            await db.execute(
                """
                INSERT INTO translation_logs (
                    article_link, target_language, translation_type,
                    translated_text, translation_service, success, error_message
                )
                VALUES (?, ?, 'summary', ?, ?, ?, ?)
                """,
                (article_link, target_language, summary, translation_service, success, error_message)
            )
        
        await db.commit()
        
        # 檢查是否有行被更新
        async with db.execute("SELECT changes()") as cur:
            row = await cur.fetchone()
            return bool(row[0])


async def get_translation_stats() -> Dict[str, Any]:
    """
    獲取詳細的翻譯統計資訊
    
    Returns:
        翻譯統計字典
    """
    async with aiosqlite.connect(DB_FILE) as db:
        stats = {}
        
        # 總文章數
        async with db.execute("SELECT COUNT(*) FROM articles") as cur:
            stats["total_articles"] = (await cur.fetchone())[0]
        
        # 按語言統計翻譯完成情況
        for lang in ["zh_tw", "zh_cn", "en"]:
            async with db.execute(f"""
                SELECT COUNT(*) FROM articles WHERE title_{lang} IS NOT NULL
            """) as cur:
                stats[f"translated_{lang}"] = (await cur.fetchone())[0]
        
        # 未翻譯文章統計
        async with db.execute("""
            SELECT COUNT(*) FROM articles
            WHERE title_zh_tw IS NULL AND title_zh_cn IS NULL AND title_en IS NULL
        """) as cur:
            stats["untranslated"] = (await cur.fetchone())[0]
        
        return stats


async def get_translation_logs(
    article_link: Optional[str] = None,
    target_language: Optional[str] = None,
    limit: int = 100,
    since: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    獲取翻譯日誌
    
    Args:
        article_link: 可選的文章URL過濾
        target_language: 可選的目標語言過濾
        limit: 返回記錄數限制
        since: 可選的時間過濾（ISO格式字串）
        
    Returns:
        翻譯日誌列表
    """
    conditions = []
    params = []
    
    if article_link:
        conditions.append("article_link = ?")
        params.append(article_link)
    
    if target_language:
        conditions.append("target_language = ?")
        params.append(target_language)
    
    if since:
        conditions.append("created_at > ?")
        params.append(since)
    
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    query = f"""
        SELECT
            id, article_link, target_language, translation_type,
            original_text, translated_text, translation_service,
            datetime(created_at) as created_at, success, error_message
        FROM translation_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# 向後相容性函數
async def update_article_translation_by_id(
    article_id: int,
    title_zh_tw: Optional[str] = None,
    title_en: Optional[str] = None,
    content_zh_tw: Optional[str] = None,
    content_en: Optional[str] = None,
    original_language: Optional[str] = None,
) -> bool:
    """
    向後相容性函數 - 在新結構中無法使用
    """
    return False


async def ensure_url_uniqueness() -> Dict[str, int]:
    """
    確保URL的唯一性統計（在新結構中URL已經是主鍵）
    
    Returns:
        統計資訊
    """
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*) FROM articles") as cur:
            total_articles = (await cur.fetchone())[0]
        
        async with db.execute("SELECT COUNT(*) FROM articles WHERE link IS NULL OR link = ''") as cur:
            empty_urls = (await cur.fetchone())[0]
        
        return {
            "removed_duplicates": 0,
            "remaining_articles": total_articles,
            "empty_urls": empty_urls
        }