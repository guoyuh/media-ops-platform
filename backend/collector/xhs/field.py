from enum import Enum


class SearchSortType(Enum):
    """搜索排序类型"""
    GENERAL = "general"
    MOST_POPULAR = "popularity_descending"
    LATEST = "time_descending"


class SearchNoteType(Enum):
    """搜索笔记类型"""
    ALL = 0
    VIDEO = 1
    IMAGE = 2
