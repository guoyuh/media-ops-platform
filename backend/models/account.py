from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, func
from database import Base


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False, default="bilibili")
    account_name = Column(String(128), nullable=False)
    cookies = Column(Text)
    is_active = Column(Boolean, default=True)
    daily_limit = Column(Integer, default=20)
    used_today = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
