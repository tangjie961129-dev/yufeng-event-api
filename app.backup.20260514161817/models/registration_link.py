"""专属填表链接模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class RegistrationLink(Base):
    __tablename__ = "registration_links"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    employee_userid = Column(String(100), nullable=False, index=True)
    customer_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending", index=True)  # pending | used
    submit_result = Column(Text, nullable=True)  # 提交结果简介
