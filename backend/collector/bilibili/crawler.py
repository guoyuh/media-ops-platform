import asyncio
from collector.base import AbstractCrawler
from collector.bilibili.client import BilibiliApiClient, _extract_mid
from config import settings


class BilibiliCrawler(AbstractCrawler):
    platform = "bilibili"

    def __init__(self):
        self.client = BilibiliApiClient()

    async def collect(self, task) -> dict | list:
        if task.task_type == "keyword":
            return await self._search_users(task.keyword, task.max_count)
        if task.task_type == "video_comment":
            return await self._video_comments(task.keyword, task.max_count)
        if task.task_type == "follower":
            return await self._follower_users(task.target_url, task.max_count)
        return []

    async def search(self, keyword: str, max_count: int) -> dict:
        return await self._video_comments(keyword, max_count)

    # ── keyword search (user) ───────────────────────────────────

    async def _search_users(self, keyword: str, max_count: int) -> list[dict]:
        users: list[dict] = []
        page = 1
        while len(users) < max_count:
            result_list = await self.client.search_users(keyword, page)
            if not result_list:
                break
            for item in result_list:
                if len(users) >= max_count:
                    break
                mid = str(item.get("mid", ""))
                detail = await self.client.get_user_card(mid)
                users.append({
                    "mid": mid,
                    "name": item.get("uname", ""),
                    "face": item.get("upic", ""),
                    "sign": item.get("usign", ""),
                    **detail,
                })
                await asyncio.sleep(1.0)
            page += 1
        return users

    # ── video_comment ───────────────────────────────────────────

    async def _video_comments(self, keyword: str, max_count: int) -> dict:
        videos = await self._search_videos_list(keyword, limit=10)
        comments: list[dict] = []
        per_video = max(max_count // max(len(videos), 1), 20)
        for v in videos:
            batch = await self._fetch_all_comments(v["aid"], per_video)
            comments.extend(batch)
        return {"videos": videos, "comments": comments}

    async def _search_videos_list(self, keyword: str, limit: int = 10) -> list[dict]:
        videos: list[dict] = []
        page = 1
        while len(videos) < limit:
            result_list = await self.client.search_videos(keyword, page)
            if not result_list:
                break
            for v in result_list:
                videos.append({
                    "aid": v.get("aid", 0),
                    "bvid": v.get("bvid", ""),
                    "title": v.get("title", ""),
                    "author": v.get("author", ""),
                    "mid": v.get("mid", 0),
                    "play_count": v.get("play", 0),
                    "like_count": v.get("like", 0),
                    "reply_count": v.get("review", 0),
                    "pubdate": v.get("pubdate", 0),
                })
                if len(videos) >= limit:
                    break
            page += 1
            await asyncio.sleep(1.0)
        return videos

    async def _fetch_all_comments(self, aid: int, remaining: int) -> list[dict]:
        comments: list[dict] = []
        pn = 1
        while len(comments) < remaining:
            data = await self.client.fetch_comments(aid, pn)
            replies = data.get("replies") or []
            if not replies:
                break
            for r in replies:
                if len(comments) >= remaining:
                    break
                comments.append(self._parse_reply(r, aid))
                sub_replies = r.get("replies") or []
                for sr in sub_replies:
                    if len(comments) >= remaining:
                        break
                    comments.append(self._parse_reply(sr, aid))
                rcount = r.get("rcount", 0)
                if rcount > len(sub_replies) and len(comments) < remaining:
                    extra = await self._fetch_sub(
                        aid, r["rpid"], remaining - len(comments), len(sub_replies)
                    )
                    comments.extend(extra)
            page_info = data.get("page", {})
            total_pages = (
                (page_info.get("count", 0) + page_info.get("size", 20) - 1)
                // max(page_info.get("size", 20), 1)
            ) if page_info else 1
            if pn >= total_pages:
                break
            pn += 1
            await asyncio.sleep(0.5)
        return comments

    async def _fetch_sub(
        self, aid: int, root_rpid: int, remaining: int, already_have: int
    ) -> list[dict]:
        subs: list[dict] = []
        pn = 2
        while len(subs) < remaining:
            data = await self.client.fetch_sub_replies(aid, root_rpid, pn)
            replies = data.get("replies") or []
            if not replies:
                break
            for sr in replies:
                if len(subs) >= remaining:
                    break
                subs.append(self._parse_reply(sr, aid))
            page_info = data.get("page", {})
            total = page_info.get("count", 0)
            if already_have + len(subs) >= total:
                break
            pn += 1
            await asyncio.sleep(0.5)
        return subs

    @staticmethod
    def _parse_reply(r: dict, aid: int) -> dict:
        member = r.get("member", {})
        content = r.get("content", {})
        return {
            "rpid": r.get("rpid", 0),
            "aid": aid,
            "mid": member.get("mid", 0),
            "uname": member.get("uname", ""),
            "avatar": member.get("avatar", ""),
            "message": content.get("message", ""),
            "like_count": r.get("like", 0),
            "ctime": r.get("ctime", 0),
            "parent_rpid": r.get("root", 0),
        }

    # ── follower / following list ───────────────────────────────

    async def _follower_users(self, target_url: str, max_count: int) -> list[dict]:
        mid = _extract_mid(target_url or "")
        if not mid:
            raise ValueError(f"无法从 '{target_url}' 提取用户 mid")
        cookie = settings.BILIBILI_COOKIE
        users: list[dict] = []
        page = 1
        while len(users) < max_count:
            items = await self.client.get_followers(mid, page, cookie)
            if not items:
                break
            for item in items:
                if len(users) >= max_count:
                    break
                users.append({
                    "mid": str(item.get("mid", "")),
                    "name": item.get("uname", ""),
                    "face": item.get("face", ""),
                    "sign": item.get("sign", ""),
                    "follower_count": 0,
                    "following_count": 0,
                    "video_count": 0,
                })
            page += 1
            await asyncio.sleep(1.0)
        return users
