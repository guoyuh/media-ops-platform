from sqlalchemy import Column, Integer, String, DateTime, Text, func
from database import Base


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    template_type = Column(String(20), nullable=False)  # dm / comment
    content = Column(Text, nullable=False)
    variables = Column(String(256), default="")  # comma-separated: nickname,keyword
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
