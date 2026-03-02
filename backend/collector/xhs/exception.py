class DataFetchError(Exception):
    """数据获取失败"""


class IPBlockError(Exception):
    """IP 被封禁"""


class NoteNotFoundError(Exception):
    """笔记不存在或状态异常"""
