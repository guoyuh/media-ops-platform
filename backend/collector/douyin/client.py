"""抖音 API 客户端

通过 Playwright 获取 localStorage (msToken) + execjs 签名 a_bogus。
"""
import asyncio
import copy
import json
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
from playwright.async_api import Page

from collector.base import AbstractApiClient
from .exception import DataFetchError
from .field import SearchChannelType, SearchSortType, PublishTimeType
from .sign import get_a_bogus, get_web_id

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_COMMON_PARAMS = {
    "device_platform": "webapp",
    "aid": "6383",
    "channel": "channel_pc_web",
    "version_code": "190600",
    "version_name": "19.6.0",
    "update_version_code": "170400",
    "pc_client_type": "1",
    "cookie_enabled": "true",
    "browser_language": "zh-CN",
    "browser_platform": "MacIntel",
    "browser_name": "Chrome",
    "browser_version": "125.0.0.0",
    "browser_online": "true",
    "engine_name": "Blink",
    "os_name": "Mac OS",
    "os_version": "10.15.7",
    "cpu_core_num": "8",
    "device_memory": "8",
    "engine_version": "109.0",
    "platform": "PC",
    "screen_width": "2560",
    "screen_height": "1440",
    "effective_type": "4g",
    "round_trip_time": "50",
}


class DouyinApiClient(AbstractApiClient):

    def __init__(
        self,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        timeout: int = 60,
    ):
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.douyin.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _process_params(self, uri: str, params: Dict) -> None:
        """添加公共参数 + a_bogus 签名"""
        if not params:
            return
        local_storage: Dict = await self.playwright_page.evaluate(
            "() => window.localStorage"
        )
        # 从浏览器获取最新 cookies（包含动态设置的）
        browser_cookies = await self.playwright_page.context.cookies()
        fresh_cookie_str = "; ".join(
            f"{c['name']}={c['value']}" for c in browser_cookies
            if ".douyin.com" in c.get("domain", "")
        )
        if fresh_cookie_str:
            self.headers["Cookie"] = fresh_cookie_str

        ms_token = local_storage.get("xmst", "")
        logger.info(f"msToken={'present' if ms_token else 'EMPTY'}, fresh_cookies={len(browser_cookies)}")

        params.update({
            **_COMMON_PARAMS,
            "webid": get_web_id(),
            "msToken": ms_token,
        })
        query_string = urllib.parse.urlencode(params)
        # 搜索接口不需要 a_bogus
        if "/v1/web/general/search" not in uri:
            params["a_bogus"] = get_a_bogus(
                uri, query_string, self.headers["User-Agent"]
            )

    async def request(self, method: str, url: str, **kwargs) -> dict:
        client = await self._get_client()
        response = await client.request(method, url, **kwargs)
        logger.info(f"HTTP {method} {url.split('?')[0]} → {response.status_code}")
        text = response.text
        if not text or text == "blocked":
            raise DataFetchError(f"Empty or blocked response: {text[:200]}")
        try:
            return response.json()
        except Exception as e:
            raise DataFetchError(f"JSON decode error: {e}, body={text[:200]}")

    async def get(self, uri: str, params: Optional[Dict] = None,
                  headers: Optional[Dict] = None) -> dict:
        await self._process_params(uri, params)
        h = copy.copy(headers or self.headers)
        h.pop("Content-Type", None)  # GET 请求不需要 Content-Type
        return await self.request(
            "GET", f"{self._host}{uri}", params=params, headers=h
        )

    async def post(self, uri: str, data: dict = None) -> dict:
        await self._process_params(uri, data)
        return await self.request(
            "POST", f"{self._host}{uri}", json=data, headers=self.headers
        )

    # ── 业务 API ─────────────────────────────────────────────

    async def search_by_keyword(
        self,
        keyword: str,
        offset: int = 0,
        search_channel: SearchChannelType = SearchChannelType.GENERAL,
        sort_type: SearchSortType = SearchSortType.GENERAL,
        publish_time: PublishTimeType = PublishTimeType.UNLIMITED,
    ) -> dict:
        uri = "/aweme/v1/web/general/search/single/"
        params = {
            "search_channel": search_channel.value,
            "enable_history": "1",
            "keyword": keyword,
            "search_source": "tab_search",
            "query_correct_type": "1",
            "is_filter_search": "0",
            "from_group_id": "",
            "offset": offset,
            "count": "15",
            "need_filter_settings": "1",
            "list_type": "multi",
        }
        if (sort_type != SearchSortType.GENERAL
                or publish_time != PublishTimeType.UNLIMITED):
            params["filter_selected"] = json.dumps({
                "sort_type": str(sort_type.value),
                "publish_time": str(publish_time.value),
            })
            params["is_filter_search"] = "1"
        headers = copy.copy(self.headers)
        referer = f"https://www.douyin.com/search/{keyword}"
        headers["Referer"] = urllib.parse.quote(referer, safe=":/")
        return await self.get(uri, params, headers=headers)

    async def get_video_by_id(self, aweme_id: str) -> dict:
        params = {"aweme_id": aweme_id}
        headers = copy.copy(self.headers)
        headers.pop("Origin", None)
        res = await self.get("/aweme/v1/web/aweme/detail/", params, headers)
        return res.get("aweme_detail", {})

    async def get_comments(self, aweme_id: str, cursor: int = 0) -> dict:
        uri = "/aweme/v1/web/comment/list/"
        params = {
            "aweme_id": aweme_id,
            "cursor": cursor,
            "count": 20,
            "item_type": 0,
        }
        headers = copy.copy(self.headers)
        headers["Referer"] = f"https://www.douyin.com/video/{aweme_id}"
        return await self.get(uri, params, headers=headers)

    async def get_sub_comments(
        self, aweme_id: str, comment_id: str, cursor: int = 0
    ) -> dict:
        uri = "/aweme/v1/web/comment/list/reply/"
        params = {
            "comment_id": comment_id,
            "cursor": cursor,
            "count": 20,
            "item_type": 0,
            "item_id": aweme_id,
        }
        return await self.get(uri, params)

    async def get_all_comments(
        self,
        aweme_id: str,
        crawl_interval: float = 1.0,
        max_count: int = 10,
    ) -> List[Dict]:
        result: List[Dict] = []
        has_more = 1
        cursor = 0
        while has_more and len(result) < max_count:
            res = await self.get_comments(aweme_id, cursor)
            has_more = res.get("has_more", 0)
            cursor = res.get("cursor", 0)
            comments = res.get("comments") or []
            status_code = res.get("status_code", -1)
            # 记录完整响应键以便调试
            logger.info(
                f"get_comments aweme_id={aweme_id} cursor={cursor} "
                f"status_code={status_code} has_more={has_more} "
                f"got={len(comments)} keys={list(res.keys())}"
            )
            if status_code != 0:
                logger.warning(
                    f"评论接口返回异常 status_code={status_code} "
                    f"aweme_id={aweme_id}"
                )
                break
            if not comments:
                break
            if len(result) + len(comments) > max_count:
                comments = comments[: max_count - len(result)]
            result.extend(comments)
            await asyncio.sleep(crawl_interval)
        return result
