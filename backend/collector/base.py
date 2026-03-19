from abc import ABC, abstractmethod


class AbstractApiClient(ABC):
    """HTTP 客户端基类，负责请求签名和发送"""

    @abstractmethod
    async def request(self, method: str, url: str, **kwargs) -> dict:
        ...

    async def get(self, uri: str, params=None) -> dict:
        return await self.request("GET", uri, params=params)

    async def post(self, uri: str, data=None) -> dict:
        return await self.request("POST", uri, data=data)


class AbstractCrawler(ABC):
    """采集流程编排基类"""
    platform: str = ""

    @abstractmethod
    async def search(self, keyword: str, max_count: int, cookie_str: str = "") -> dict:
        ...

    async def collect(self, task, cookie_str: str = "") -> dict | list:
        """默认入口，子类可覆盖以支持多种 task_type"""
        return await self.search(task.keyword, task.max_count, cookie_str=cookie_str)
