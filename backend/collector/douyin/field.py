from enum import Enum


class SearchChannelType(Enum):
    GENERAL = "aweme_general"
    VIDEO = "aweme_video_web"


class SearchSortType(Enum):
    GENERAL = 0
    MOST_LIKE = 1
    LATEST = 2


class PublishTimeType(Enum):
    UNLIMITED = 0
    ONE_DAY = 1
    ONE_WEEK = 7
    SIX_MONTH = 180
