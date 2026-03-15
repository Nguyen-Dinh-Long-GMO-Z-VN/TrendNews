"""
Vietnam RSS Fetcher for TrendRadar.

Fetches news from Vietnamese news sites via RSS feeds,
returning data in the same format as DataFetcher.crawl_websites().
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests


class VietnamRSSFetcher:
    """Fetches news from Vietnamese RSS feeds."""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        if proxy_url:
            self.session.proxies = {"http": proxy_url, "https": proxy_url}

    def fetch_rss(self, platform_id: str, rss_url: str, name: str) -> Optional[Dict]:
        """
        Fetch and parse an RSS feed.

        Returns:
            Dict of {title: {"ranks": [rank], "url": url, "mobileUrl": ""}}
            or None on failure.
        """
        try:
            from src.config.settings import CONFIG
            max_items = CONFIG.get("RSS_MAX_ITEMS", 50)
        except Exception:
            max_items = 50

        try:
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            content = response.text

            items = self._parse_rss_items(content, max_items=max_items)
            if not items:
                print(f"Lấy {platform_id} thất bại（không parse được RSS）")
                return None

            result = {}
            for rank, (title, url) in enumerate(items, 1):
                if not title.strip():
                    continue
                result[title.strip()] = {
                    "ranks": [rank],
                    "url": url,
                    "mobileUrl": "",
                }

            print(f"Lấy {platform_id} thành công（dữ liệu mới nhất）")
            return result

        except Exception as e:
            print(f"Lấy {platform_id} thất bại: {e}")
            return None

    def _parse_rss_items(self, content: str, max_items: int = 50) -> List[Tuple[str, str]]:
        """Extract (title, url) pairs from RSS XML string."""
        items = []

        # Find all <item> blocks
        item_blocks = re.findall(r"<item[^>]*>(.*?)</item>", content, re.DOTALL)

        for block in item_blocks[:max_items]:
            # Extract title: supports CDATA and plain text
            title_match = re.search(
                r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",
                block, re.DOTALL
            )
            title = ""
            if title_match:
                title = (title_match.group(1) or title_match.group(2) or "").strip()

            # Extract link
            # Check self-closing <link/> explicitly before regex
            is_self_closing = bool(re.search(r"<link\s*/>", block))

            link_match = re.search(
                r"<link><!\[CDATA\[(.*?)\]\]></link>"
                r"|<link>(.+?)</link>",   # use .+ (one or more) so empty match is rejected
                block, re.DOTALL
            )
            guid_match = re.search(r"<guid[^>]*>(https?://[^<]+)</guid>", block)

            url = ""
            if not is_self_closing and link_match:
                url = (link_match.group(1) or link_match.group(2) or "").strip()
            if not url and guid_match:
                url = guid_match.group(1).strip()

            if title:
                items.append((title, url))

        return items

    def crawl_vietnam_platforms(
        self,
        platforms: List[Dict],
        request_interval: int = 1000,
        max_workers: int = 24,
    ) -> Tuple[Dict, Dict, List]:
        """
        Crawl RSS platforms concurrently using ThreadPoolExecutor.

        Args:
            platforms: List of platform dicts with keys: id, name, rss_url
            request_interval: Kept for backward compatibility (ignored in concurrent mode)
            max_workers: Maximum number of concurrent threads

        Returns:
            Tuple of (results, id_to_name, failed_ids)
        """
        results = {}
        id_to_name = {}
        failed_ids = []

        # Pre-build id_to_name and filter out platforms without rss_url
        valid_platforms = []
        for platform in platforms:
            pid = platform["id"]
            name = platform.get("name", pid)
            id_to_name[pid] = name
            rss_url = platform.get("rss_url", "")
            if not rss_url:
                print(f"Bỏ qua {pid}: không có rss_url")
                failed_ids.append(pid)
            else:
                valid_platforms.append((pid, rss_url, name))

        def _fetch(args: tuple) -> tuple:
            pid, rss_url, name = args
            return pid, self.fetch_rss(pid, rss_url, name)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pid = {
                executor.submit(_fetch, p): p[0] for p in valid_platforms
            }
            for future in as_completed(future_to_pid):
                pid, data = future.result()
                if data is not None:
                    results[pid] = data
                else:
                    failed_ids.append(pid)

        return results, id_to_name, failed_ids
