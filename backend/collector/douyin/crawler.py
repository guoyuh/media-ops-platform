"""抖音采集器

搜索视频 + 采集评论，架构与 XhsCrawler 一致。
"""
import asyncio
import logging
import os
from typing import Dict, List

from playwright.async_api import async_playwright

from collector.base import AbstractCrawler
from .client import DouyinApiClient, _USER_AGENT

logger = logging.getLogger(__name__)

_STEALTH_JS = os.path.join(
    os.path.dirname(__file__), "..", "..", "libs", "stealth.min.js"
)

_DOUYIN_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.douyin.com",
    "Origin": "https://www.douyin.com",
    "Content-Type": "application/json;charset=UTF-8",
}


def _parse_cookie_str(cookie_str: str) -> dict:
    result = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


class DouyinCrawler(AbstractCrawler):
    platform = "douyin"

    async def collect(self, task, cookie_str: str = "") -> dict:
        return await self.search(
            task.keyword, task.max_count, cookie_str=cookie_str
        )

    async def search(
        self, keyword: str, max_count: int, cookie_str: str = ""
    ) -> dict:
        if not cookie_str:
            raise ValueError(
                "Cookie 未提供，请在账号管理中配置抖音账号"
            )
        cookie_dict = _parse_cookie_str(cookie_str)
        headers = {**_DOUYIN_HEADERS, "Cookie": cookie_str}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=headers["User-Agent"]
            )
            if os.path.exists(_STEALTH_JS):
                await context.add_init_script(path=_STEALTH_JS)
            await context.add_cookies([
                {
                    "name": k, "value": v,
                    "domain": ".douyin.com", "path": "/"
                }
                for k, v in cookie_dict.items()
            ])
            page = await context.new_page()
            await page.goto(
                "https://www.douyin.com",
                wait_until="domcontentloaded",
            )
            # 等待页面 JS 执行完毕，生成 msToken 等动态 cookie
            await asyncio.sleep(5)

            client = DouyinApiClient(
                headers=headers,
                playwright_page=page,
                cookie_dict=cookie_dict,
            )

            try:
                videos = await self._search_videos(
                    client, keyword, max_count
                )
                comments = await self._fetch_all_comments(
                    client, videos
                )
            finally:
                await client.close()
                await browser.close()

        return {"videos": videos, "comments": comments}

    async def _search_videos(
        self, client: DouyinApiClient, keyword: str, max_count: int
    ) -> List[Dict]:
        videos: List[Dict] = []
        offset = 0
        while len(videos) < max_count:
            data = await client.search_by_keyword(keyword, offset=offset)
            items = data.get("data") or []
            if not items:
                break
            for item in items:
                if len(videos) >= max_count:
                    break
                aweme = item.get("aweme_info")
                if not aweme:
                    continue
                stats = aweme.get("statistics", {})
                author = aweme.get("author", {})
                videos.append({
                    "aweme_id": aweme.get("aweme_id", ""),
                    "desc": aweme.get("desc", ""),
                    "author_uid": author.get("uid", ""),
                    "author_nickname": author.get("nickname", ""),
                    "author_avatar": (
                        author.get("avatar_thumb", {})
                        .get("url_list", [""])[0]
                    ),
                    "digg_count": stats.get("digg_count", 0),
                    "comment_count": stats.get("comment_count", 0),
                    "share_count": stats.get("share_count", 0),
                    "play_count": stats.get("play_count", 0),
                    "create_time": aweme.get("create_time", 0),
                })
            offset += 15
            await asyncio.sleep(1.0)
        return videos

    async def _fetch_all_comments(
        self, client: DouyinApiClient, videos: List[Dict]
    ) -> List[Dict]:
        comments: List[Dict] = []
        for video in videos:
            aweme_id = video["aweme_id"]
            try:
                logger.info(
                    f"开始获取视频 {aweme_id} 的评论"
                )
                raw = await client.get_all_comments(
                    aweme_id, max_count=20
                )
                logger.info(
                    f"视频 {aweme_id} 获取到 {len(raw)} 条评论"
                )
                for c in raw:
                    user = c.get("user", {})
                    cid = c.get("cid", "")
                    if not cid:
                        continue
                    comments.append({
                        "cid": str(cid),
                        "aweme_id": aweme_id,
                        "text": c.get("text", ""),
                        "user_id": str(user.get("uid", "")),
                        "nickname": user.get("nickname", ""),
                        "avatar": (
                            user.get("avatar_thumb", {})
                            .get("url_list", [""])[0]
                        ),
                        "digg_count": c.get("digg_count", 0),
                        "reply_comment_total": c.get(
                            "reply_comment_total", 0
                        ),
                        "create_time": c.get("create_time", 0),
                        "ip_location": c.get("ip_label", ""),
                    })
            except Exception as e:
                logger.warning(
                    f"获取视频 {aweme_id} 评论失败: {e}",
                    exc_info=True,
                )
            await asyncio.sleep(1.0)
        logger.info(f"评论采集完成，共 {len(comments)} 条")
        return comments
