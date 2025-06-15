"""
自動化任務調度器
實現每10分鐘自動抓取RSS新聞的背景任務
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .rss_fetcher import fetch_and_store_news, translate_missing_articles
from .db import get_translation_stats

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsScheduler:
    """新聞自動化調度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_fetch_time: Optional[datetime] = None
        self.last_fetch_result: Optional[Dict[str, Any]] = None
        self.fetch_enabled = True
        self.translation_enabled = True
        self._fetch_in_progress = False  # 添加執行狀態標記
        
        # 設置事件監聽器
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
    
    def _job_executed(self, event):
        """任務執行成功回調"""
        logger.info(f"任務執行成功: {event.job_id} at {datetime.now()}")
    
    def _job_error(self, event):
        """任務執行錯誤回調"""
        logger.error(f"任務執行失敗: {event.job_id}, 錯誤: {event.exception}")
    
    async def _fetch_news_job(self):
        """
        自動抓取新聞任務
        新流程：抓取RSS → 即時翻譯 → 儲存完整資料
        強化執行狀態檢查，防止重複執行
        """
        if not self.fetch_enabled:
            logger.info("新聞抓取已停用，跳過此次執行")
            return
        
        # 強化執行狀態檢查
        if self._fetch_in_progress:
            logger.warning("上一次抓取任務仍在執行中，跳過此次執行")
            return
            
        try:
            self._fetch_in_progress = True
            start_time = datetime.now()
            logger.info(f"開始自動抓取新聞（包含即時翻譯）... 開始時間: {start_time}")
            
            # 根據翻譯設定決定是否進行即時翻譯
            if self.translation_enabled:
                logger.info("執行完整抓取流程（包含即時翻譯）")
                result = await fetch_and_store_news()
            else:
                logger.info("執行快速抓取流程（跳過翻譯）")
                from .rss_fetcher import refresh_feeds_fast
                result = await refresh_feeds_fast()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.last_fetch_time = end_time
            self.last_fetch_result = result
            
            logger.info(f"新聞抓取完成，耗時 {duration:.2f} 秒: {result}")
                
        except Exception as e:
            logger.error(f"自動抓取新聞失敗: {str(e)}")
            self.last_fetch_result = {"error": str(e)}
        finally:
            self._fetch_in_progress = False
            logger.info("抓取任務執行狀態已重置")
    
    async def _cleanup_job(self):
        """定期清理任務（每小時執行一次）"""
        try:
            logger.info("開始定期清理任務...")
            from .db import ensure_url_uniqueness, delete_old_articles
            result = await ensure_url_uniqueness()
            deleted_count = await delete_old_articles(7)
            logger.info(f"清理完成: {result}，刪除7天前新聞數量: {deleted_count}")
        except Exception as e:
            logger.error(f"定期清理失敗: {str(e)}")
    
    def start(self):
        """啟動調度器"""
        if self.is_running:
            logger.warning("調度器已在運行中")
            return
        
        try:
            # 添加新聞抓取任務（每10分鐘）
            self.scheduler.add_job(
                self._fetch_news_job,
                trigger=IntervalTrigger(minutes=10),
                id='fetch_news',
                name='自動抓取新聞',
                replace_existing=True,
                max_instances=1  # 防止重複執行
            )
            
            # 添加清理任務（每小時）
            self.scheduler.add_job(
                self._cleanup_job,
                trigger=IntervalTrigger(hours=1),
                id='cleanup',
                name='定期清理',
                replace_existing=True,
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("調度器啟動成功")
            
        except Exception as e:
            logger.error(f"調度器啟動失敗: {str(e)}")
            raise
    
    def stop(self):
        """停止調度器"""
        if not self.is_running:
            logger.warning("調度器未在運行")
            return
        
        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("調度器已停止")
        except Exception as e:
            logger.error(f"調度器停止失敗: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """獲取調度器狀態"""
        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
        
        return {
            'is_running': self.is_running,
            'fetch_enabled': self.fetch_enabled,
            'translation_enabled': self.translation_enabled,
            'fetch_in_progress': self._fetch_in_progress,  # 添加執行狀態
            'last_fetch_time': self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            'last_fetch_result': self.last_fetch_result,
            'jobs': jobs
        }
    
    def enable_fetch(self, enabled: bool = True):
        """啟用/停用新聞抓取"""
        self.fetch_enabled = enabled
        logger.info(f"新聞抓取已{'啟用' if enabled else '停用'}")
    
    def enable_translation(self, enabled: bool = True):
        """啟用/停用自動翻譯"""
        self.translation_enabled = enabled
        logger.info(f"自動翻譯已{'啟用' if enabled else '停用'}")
    
    async def trigger_fetch_now(self) -> Dict[str, Any]:
        """立即觸發新聞抓取"""
        if self._fetch_in_progress:
            logger.warning("抓取任務正在執行中，無法手動觸發")
            return {"error": "抓取任務正在執行中，請稍後再試"}
        
        logger.info("手動觸發新聞抓取...")
        await self._fetch_news_job()
        return self.last_fetch_result or {}

# 全局調度器實例
_scheduler_instance: Optional[NewsScheduler] = None

def get_scheduler() -> NewsScheduler:
    """獲取調度器實例（單例模式）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = NewsScheduler()
    return _scheduler_instance

async def start_scheduler():
    """啟動調度器"""
    scheduler = get_scheduler()
    scheduler.start()

async def stop_scheduler():
    """停止調度器"""
    scheduler = get_scheduler()
    scheduler.stop()