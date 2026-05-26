"""会员档案表 — 来自专属填表链接的数据（完整26项字段）"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class MemberProfile(Base):
    """会员完整档案（匹配引擎数据源）"""
    __tablename__ = "member_profiles"

    id = Column(Integer, primary_key=True, index=True)
    external_userid = Column(String(100), nullable=True, index=True)
    employee_userid = Column(String(100), default="")
    token = Column(String(64), unique=True, nullable=True)
    source = Column(String(50), default="")
    tags_applied = Column(Text, default="[]")

    # ===== 第一步：基本 =====
    nickname = Column(String(100), default="")
    city = Column(String(100), default="")
    wechat = Column(String(100), default="")
    phone = Column(String(30), default="")
    hometown = Column(String(100), default="")
    birth_info = Column(String(50), default="")
    income = Column(String(30), default="")
    job = Column(String(100), default="")
    education = Column(String(50), default="")

    # ===== 第二步：外貌 =====
    height = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    body_type = Column(String(30), default="")
    ideal_body_type = Column(String(100), default="")

    # ===== 第三步：角色 =====
    role_self = Column(String(20), default="")
    ideal_role = Column(String(20), default="")

    # ===== 第四步：现状 =====
    single_duration = Column(String(50), default="")
    out_status = Column(String(100), default="")
    marriage = Column(String(50), default="")
    attitude_live = Column(Text, default="")
    experience = Column(String(100), default="")

    # ===== 第五步：性格 =====
    self_tags = Column(String(500), default="")
    ideal_type_tags = Column(String(500), default="")
    dealbreaker = Column(Text, default="")
    long_distance = Column(String(30), default="")
    social_info = Column(Text, default="")

    # ===== 第六步：期待 =====
    ideal_desc = Column(Text, default="")
    love_habits = Column(Text, default="")
    why_together = Column(Text, default="")
    extra_message = Column(Text, default="")

    photo_path = Column(String(500), default="")
    photos = Column(Text, default="[]")

    # 旧字段保留兼容
    lifestyle_status = Column(Text, default="")
    hobbies = Column(Text, default="")
    current_situation = Column(Text, default="")
    expectation = Column(Text, default="")

    # S/A/B/C 分层评分
    level = Column(String(2), default="", comment="运营层级 S/A/B/C")
    level_score = Column(Integer, nullable=True, comment="层级评分(0-100)")
    
    # 最后一次跟进时间
    last_contact_at = Column(DateTime(timezone=True), nullable=True, comment="最后一次员工跟进时间")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
