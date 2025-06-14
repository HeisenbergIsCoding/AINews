from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Dict, Optional, Tuple, List
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class TranslationService:
    """優化的OpenAI翻譯服務類別"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化翻譯服務
        
        Args:
            api_key: OpenAI API金鑰，如果未提供則從環境變數讀取
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # 使用更經濟的模型
        
        # API速率限制控制
        self.last_api_call = 0
        self.min_interval = 1.0  # 最小間隔1秒
        self.max_retries = 3
        self.retry_delay = 2.0
        
    
    async def _rate_limit_wait(self):
        """API速率限制控制"""
        current_time = time.time()
        time_since_last = current_time - self.last_api_call
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)
        self.last_api_call = time.time()
    
    async def translate_with_auto_detection(self, title: str, content: str) -> Dict[str, str]:
        """
        使用AI自動檢測語言並翻譯文章
        
        Args:
            title: 文章標題
            content: 文章內容
            
        Returns:
            包含翻譯結果的字典
        """
        if not title and not content:
            return {
                'original_language': 'unknown',
                'title_zh_tw': None,
                'title_en': None,
                'title_zh_cn': None,
                'content_zh_tw': None,
                'content_en': None,
                'content_zh_cn': None,
                'translation_status': 'failed'
            }
            
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_wait()
                
                # 組合文本用於語言檢測和翻譯
                combined_text = f"標題: {title}\n內容: {content}" if title and content else (title or content)
                
                system_prompt = """你是一個專業的多語言翻譯專家。請分析給定的文本，自動檢測其語言，然後根據以下規則進行翻譯：

1. 如果是繁體中文 → 翻譯成英文 + 簡體中文
2. 如果是英文 → 翻譯成繁體中文 + 簡體中文
3. 如果是簡體中文 → 翻譯成繁體中文 + 英文

請以JSON格式回應，包含以下欄位：
- original_language: 檢測到的原始語言 ("zh-tw", "en", "zh-cn", "other")
- title_zh_tw: 繁體中文標題（不要包含語言標籤）
- title_en: 英文標題（不要包含語言標籤）
- title_zh_cn: 簡體中文標題（不要包含語言標籤）
- content_zh_tw: 繁體中文內容（不要包含語言標籤）
- content_en: 英文內容（不要包含語言標籤）
- content_zh_cn: 簡體中文內容（不要包含語言標籤）

重要：翻譯結果中不要包含任何語言標籤（如「原始语言: en」等），只提供純粹的翻譯內容。確保翻譯自然流暢，保持原文的語調和風格。"""

                user_prompt = f"請分析並翻譯以下文本：\n\n{combined_text}"
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=3000,
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                import json
                result = json.loads(response.choices[0].message.content)
                result['translation_status'] = 'completed'
                return result
                
            except Exception as e:
                logger.warning(f"Translation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"Translation failed after {self.max_retries} attempts: {e}")
                    return {
                        'original_language': 'unknown',
                        'title_zh_tw': title if title else None,
                        'title_en': title if title else None,
                        'title_zh_cn': title if title else None,
                        'content_zh_tw': content if content else None,
                        'content_en': content if content else None,
                        'content_zh_cn': content if content else None,
                        'translation_status': 'failed'
                    }
    
    async def translate_article(self, title: str, content: str) -> Dict[str, str]:
        """
        翻譯文章標題和內容，使用AI自動檢測語言並翻譯
        
        Args:
            title: 文章標題
            content: 文章內容
            
        Returns:
            包含翻譯結果的字典
        """
        try:
            # 使用新的AI自動檢測和翻譯方法
            result = await self.translate_with_auto_detection(title, content)
            
            # 確保結果包含所有必要的欄位
            if 'translation_status' not in result:
                result['translation_status'] = 'completed'
                
            return result
            
        except Exception as e:
            logger.error(f"Article translation failed: {e}")
            return {
                'original_language': 'unknown',
                'title_zh_tw': title,
                'title_en': title,
                'content_zh_tw': content,
                'content_en': content,
                'translation_status': 'failed'
            }
    
    async def batch_translate_articles(self, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        批次翻譯多篇文章
        
        Args:
            articles: 文章列表，每個包含title、content和link
            
        Returns:
            翻譯結果列表
        """
        results = []
        
        for i, article in enumerate(articles):
            logger.info(f"Translating article {i + 1}/{len(articles)}: {article.get('title', '')[:50]}...")
            
            try:
                result = await self.translate_article(
                    article.get('title', ''),
                    article.get('summary', article.get('content', ''))  # 使用summary作為content
                )
                result['article_link'] = article.get('link')  # 使用link而不是id
                results.append(result)
                
                # 批次處理間隔
                if i < len(articles) - 1:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Failed to translate article {i + 1}: {e}")
                results.append({
                    'article_link': article.get('link'),
                    'translation_status': 'failed',
                    'error': str(e)
                })
        
        return results

# 全域翻譯服務實例
_translation_service: Optional[TranslationService] = None

def get_translation_service() -> TranslationService:
    """獲取翻譯服務實例"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service

async def translate_article_content(title: str, content: str) -> Dict[str, str]:
    """
    翻譯文章內容的便利函數
    
    Args:
        title: 文章標題
        content: 文章內容
        
    Returns:
        翻譯結果字典
    """
    service = get_translation_service()
    return await service.translate_article(title, content)