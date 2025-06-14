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
    "https://www.technologyreview.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    # — Chinese / Taiwanese sources —
    "https://technews.tw/category/ai/feed",
    "http://www.jiqizhixin.com/rss",
    "https://www.qbitai.com/feed",
]