from __future__ import annotations

"""
Central list of RSS feed URLs aggregated by the application.

You can freely add or remove URLs from the FEEDS list and simply
restart the FastAPI server to apply the change.
"""

from typing import List

FEEDS: List[str] = [
    # — English sources —
    "https://www.artificialintelligence-news.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.wired.com/feed/category/ai/latest/rss",
    "https://www.technologyreview.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.forbes.com/ai/feed/",
    # — Chinese / Taiwanese sources —
    "https://technews.tw/category/ai/feed",
    "https://36kr.com/information/web_news/%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD?format=feed",
    "http://www.jiqizhixin.com/rss",
    "https://www.qbitai.com/feed",
]