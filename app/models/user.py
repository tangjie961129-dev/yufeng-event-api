"""
用户模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    openid = Column(String(100), unique=True, index=True, nullable=False)
    nickname = Column(String(50), default="")
    avatar_url = Column(String(500), default="")
    phone = Column(String(20), unique=True, nullable=True)

    # 企微客户身份（用于自动打标签）
    external_userid = Column(String(100), unique=True, nullable=True, index=True)

    # 认证相关
    is_organizer = Column(Boolean, default=False)       # 是否认证主办方
    organizer_verified = Column(Boolean, default=False)  # 认证是否通过

    # 匹配引擎旧字段（保留）
    city = Column(String(50), default="")
    age = Column(Integer, nullable=True)
    education = Column(String(20), default="")
    income_range = Column(String(20), default="")
    personality_tags = Column(Text, default="[]")
    hobby_tags = Column(Text, default="[]")
    bio = Column(Text, default="")
    match_preferences = Column(Text, default="")
    match_status = Column(String(20), default="disabled")

    # 匹配记录 / 企微群聊配置（JSON）
    match_records_json = Column(Text, default="[]")

    # 匹配次数（付费购买）
    match_credits = Column(Integer, default=0)

    # 免费测试次数（新用户注册送3次，用完走付费）
    test_remaining = Column(Integer, default=3)

    # 积分
    points = Column(Integer, default=0)
    member_level = Column(Integer, default=0)
    points_history_json = Column(Text, default="[]")

    # 封面选择（头像/生活照）
    photos = Column(Text, default="[]")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
