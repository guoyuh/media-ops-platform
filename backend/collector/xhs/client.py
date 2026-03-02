import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_not_exception_type

from collector.base import AbstractApiClient
from .exception import DataFetchError, IPBlockError, NoteNotFoundError
from .field import SearchNoteType, SearchSortType
from .sign import sign_with_playwright, get_search_id

logger = logging.getLogger(__name__)


class XhsApiClient(AbstractApiClient):

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
        self._host = "https://edith.xiaohongshu.com"
        self.IP_ERROR_CODE = 300012
        self.NOTE_NOT_FOUND_CODE = -510000
        self.NOTE_ABNORMAL_CODE = -510001
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict

    async def _pre_headers(
        self, url: str, params: Optional[Dict] = None, payload: Optional[Dict] = None
    ) -> Dict:
        a1_value = self.cookie_dict.get("a1", "")
        if params is not None:
            data, method = params, "GET"
        elif payload is not None:
            data, method = payload, "POST"
        else:
            raise ValueError("params or payload is required")
        signs = await sign_with_playwright(
            page=self.playwright_page, uri=url, data=data, a1=a1_value, method=method,
        )
        self.headers.update({
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        })
        return self.headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1),
           retry=retry_if_not_exception_type(NoteNotFoundError))
    async def request(self, method, url, **kwargs) -> Union[str, Any]:
        return_response = kwargs.pop("return_response", False)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, timeout=self.timeout, **kwargs)
        except Exception as e:
            logger.error(f"HTTP request failed: {method} {url} -> {e}")
            raise
        logger.info(f"XHS API: {method} {url} -> {response.status_code}")
        if response.status_code in (471, 461):
            raise Exception(f"验证码出现, status={response.status_code}")
        if return_response:
            return response.text
        data: Dict = response.json()
        if data.get("success"):
            return data.get("data", data.get("success", {}))
        elif data.get("code") == self.IP_ERROR_CODE:
            raise IPBlockError("IP 被封禁")
        elif data.get("code") in (self.NOTE_NOT_FOUND_CODE, self.NOTE_ABNORMAL_CODE):
            raise NoteNotFoundError(f"笔记不存在, code: {data.get('code')}")
        else:
            logger.error(f"XHS API error: code={data.get('code')} msg={data.get('msg')} body={response.text[:500]}")
            raise DataFetchError(data.get("msg", response.text))

    async def get(self, uri: str, params: Optional[Dict] = None) -> Dict:
        headers = await self._pre_headers(uri, params)
        return await self.request("GET", f"{self._host}{uri}", headers=headers, params=params)

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        headers = await self._pre_headers(uri, payload=data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            "POST", f"{self._host}{uri}", data=json_str, headers=headers, **kwargs,
        )

    # ── 业务 API ─────────────────────────────────────────────────

    async def get_note_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: SearchSortType = SearchSortType.GENERAL,
        note_type: SearchNoteType = SearchNoteType.ALL,
        search_id: str = "",
    ) -> Dict:
        uri = "/api/sns/web/v1/search/notes"
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": search_id or get_search_id(),
            "sort": sort.value,
            "note_type": note_type.value,
        }
        return await self.post(uri, data)

    async def get_note_by_id(
        self, note_id: str, xsec_source: str, xsec_token: str
    ) -> Dict:
        if not xsec_source:
            xsec_source = "pc_search"
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }
        res = await self.post("/api/sns/web/v1/feed", data)
        if res and res.get("items"):
            return res["items"][0]["note_card"]
        logger.warning(f"get_note_by_id empty: note_id={note_id}")
        return {}

    async def get_note_comments(
        self, note_id: str, xsec_token: str, cursor: str = ""
    ) -> Dict:
        uri = "/api/sns/web/v2/comment/page"
        params = {
            "note_id": note_id, "cursor": cursor,
            "top_comment_id": "", "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        return await self.get(uri, params)

    async def get_note_sub_comments(
        self, note_id: str, root_comment_id: str, xsec_token: str,
        num: int = 10, cursor: str = "",
    ) -> Dict:
        uri = "/api/sns/web/v2/comment/sub/page"
        params = {
            "note_id": note_id, "root_comment_id": root_comment_id,
            "num": str(num), "cursor": cursor,
            "image_formats": "jpg,webp,avif", "top_comment_id": "",
            "xsec_token": xsec_token,
        }
        return await self.get(uri, params)

    async def get_note_all_comments(
        self,
        note_id: str,
        xsec_token: str,
        crawl_interval: float = 1.0,
        max_count: int = 10,
    ) -> List[Dict]:
        result = []
        has_more = True
        cursor = ""
        while has_more and len(result) < max_count:
            res = await self.get_note_comments(note_id, xsec_token, cursor)
            has_more = res.get("has_more", False)
            cursor = res.get("cursor", "")
            comments = res.get("comments")
            if not comments:
                break
            if len(result) + len(comments) > max_count:
                comments = comments[: max_count - len(result)]
            result.extend(comments)
            await asyncio.sleep(crawl_interval)
        return result

    async def pong(self) -> bool:
        uri = "/api/sns/web/v1/user/selfinfo"
        try:
            headers = await self._pre_headers(uri, params={})
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._host}{uri}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return bool(data.get("data", {}).get("result", {}).get("success"))
        except Exception as e:
            logger.error(f"pong failed: {e}")
        return False

    async def update_cookies(self, browser_context: BrowserContext):
        cookies = await browser_context.cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict
