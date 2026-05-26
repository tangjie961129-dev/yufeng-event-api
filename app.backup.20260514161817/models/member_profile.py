"""会员档案表 — 来自专属填表链接的数据"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class MemberProfile(Base):
    """会员完整档案（匹配引擎数据源）"""
    __tablename__ = "member_profiles"

    id = Column(Integer, primary_key=True, index=True)
    external_userid = Column(String(100), nullable=True, index=True, comment="企微客户 ID")
    employee_userid = Column(String(100), default="", comment="录入员工")
    token = Column(String(64), unique=True, nullable=True, comment="填表链接 token")

    # 表单字段
    nickname = Column(String(100), default="", comment="微信昵称")
    city = Column(String(100), default="", comment="所在城市")
    age = Column(Integer, nullable=True, comment="年龄")
    height = Column(Integer, nullable=True, comment="身高(cm)")
    weight = Column(Integer, nullable=True, comment="体重(kg)")
    role_self = Column(String(20), default="", comment="性角色")
    body_type = Column(String(20), default="", comment="体型")
    job = Column(String(100), default="", comment="职业")
    income = Column(String(30), default="", comment="月收入")
    lifestyle_status = Column(Text, default="", comment="日常状态")
    hobbies = Column(Text, default="", comment="爱好与习惯")
    current_situation = Column(Text, default="", comment="目前状况")
    expectation = Column(Text, default="", comment="期待的你")
    long_distance = Column(String(20), default="", comment="是否接受短暂异地")

    # 打标签结果
    tags_applied = Column(Text, default="[]", comment="已打标签列表(JSON)")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
