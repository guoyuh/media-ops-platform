from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger, func
from database import Base


class DouyinVideo(Base):
    __tablename__ = "douyin_videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    aweme_id = Column(String(64), nullable=False, index=True)
    desc = Column(Text)
    author_uid = Column(String(64))
    author_nickname = Column(String(128))
    author_avatar = Column(Text)
    digg_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    play_count = Column(Integer, default=0)
    create_time = Column(BigInteger, default=0)
    source_task_id = Column(Integer, index=True)
    created_at = Column(DateTime, server_default=func.now())


class DouyinComment(Base):
    __tablename__ = "douyin_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cid = Column(String(64), nullable=False, index=True)
    aweme_id = Column(String(64), index=True)
    text = Column(Text)
    user_id = Column(String(64))
    nickname = Column(String(128))
    avatar = Column(Text)
    digg_count = Column(Integer, default=0)
    reply_comment_total = Column(Integer, default=0)
    create_time = Column(BigInteger, default=0)
    ip_location = Column(String(64))
    parent_cid = Column(String(64), default="")
    source_task_id = Column(Integer, index=True)
    created_at = Column(DateTime, server_default=func.now())
