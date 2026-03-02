import re
import asyncio
import httpx
from collector.base import AbstractApiClient
from config import settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}
_API = settings.BILIBILI_API_BASE


def _extract_mid(text: str) -> str | None:
    if text.isdigit():
        return text
    m = re.search(r"space\.bilibili\.com/(\d+)", text)
    return m.group(1) if m else None


def _make_client(cookie: str = "") -> httpx.AsyncClient:
    headers = {**_HEADERS}
    if cookie:
        headers["Cookie"] = cookie
    return httpx.AsyncClient(timeout=15, headers=headers)


class BilibiliApiClient(AbstractApiClient):

    async def request(self, method: str, url: str, **kwargs) -> dict:
        async with _make_client() as client:
            resp = await client.request(method, url, **kwargs)
            return resp.json()

    async def search_users(self, keyword: str, page: int = 1) -> list[dict]:
        async with _make_client() as client:
            resp = await client.get(
                f"{_API}/x/web-interface/wbi/search/type",
                params={"search_type": "bili_user", "keyword": keyword, "page": page},
            )
            return resp.json().get("data", {}).get("result", [])

    async def get_user_card(self, mid: str) -> dict:
        try:
            async with _make_client() as client:
                resp = await client.get(
                    f"{_API}/x/web-interface/card", params={"mid": mid}
                )
                card = resp.json().get("data", {})
                return {
                    "follower_count": card.get("follower", 0),
                    "following_count": card.get("friend", 0),
                    "video_count": card.get("archive_count", 0),
                }
        except Exception:
            return {"follower_count": 0, "following_count": 0, "video_count": 0}

    async def search_videos(
        self, keyword: str, page: int = 1
    ) -> list[dict]:
        async with _make_client() as client:
            resp = await client.get(
                f"{_API}/x/web-interface/wbi/search/type",
                params={"search_type": "video", "keyword": keyword, "page": page},
            )
            return resp.json().get("data", {}).get("result") or []

    async def fetch_comments(
        self, aid: int, pn: int = 1, ps: int = 20
    ) -> dict:
        async with _make_client() as client:
            resp = await client.get(
                f"{_API}/x/v2/reply",
                params={"type": 1, "oid": aid, "pn": pn, "ps": ps, "sort": 2},
            )
            return resp.json().get("data", {})

    async def fetch_sub_replies(
        self, aid: int, root_rpid: int, pn: int = 1, ps: int = 20
    ) -> dict:
        async with _make_client() as client:
            resp = await client.get(
                f"{_API}/x/v2/reply/reply",
                params={"type": 1, "oid": aid, "root": root_rpid, "pn": pn, "ps": ps},
            )
            return resp.json().get("data", {})

    async def get_followers(
        self, mid: str, pn: int = 1, cookie: str = ""
    ) -> list[dict]:
        endpoint = (
            f"{_API}/x/relation/followers" if cookie
            else f"{_API}/x/relation/followings"
        )
        async with _make_client(cookie) as client:
            resp = await client.get(
                endpoint, params={"vmid": mid, "pn": pn, "ps": 20}
            )
            return resp.json().get("data", {}).get("list", [])
