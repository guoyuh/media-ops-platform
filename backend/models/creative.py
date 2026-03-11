from sqlalchemy import Column, Integer, String, DateTime, Text, func
from database import Base


class CreativePost(Base):
    __tablename__ = "creative_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), default="")
    content = Column(Text, default="")
    tags = Column(Text, default="[]")          # JSON string list
    style = Column(String(64), default="")     # 种草/测评/教程/日常分享 etc.
    topic = Column(String(256), default="")
    reference_note_ids = Column(Text, default="[]")  # JSON string list
    status = Column(String(20), default="draft")     # draft / published
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
