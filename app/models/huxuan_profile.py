"""煎面（外部合作）会员档案表模型"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class HuxuanProfile(Base):
    """煎面/线上互选会员完整档案"""
    __tablename__ = "huxuan_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # 编号系统
    编号 = Column(String(20), default="")
    屿风编号 = Column(String(20), default="")
    昵称 = Column(String(50), default="")

    # 基础信息
    城市 = Column(String(100), default="")
    年龄 = Column(String(10), default="")
    身高 = Column(String(20), default="")
    体重 = Column(String(20), default="")
    体型 = Column(String(20), default="")
    学历 = Column(String(50), default="")
    职业 = Column(String(100), default="")
    属性 = Column(String(30), default="")

    # 情感状态
    单身多久 = Column(String(50), default="")
    出柜对象 = Column(String(100), default="")
    形婚考虑 = Column(String(50), default="")
    星座MBTI = Column(String(50), default="")
    约会状态 = Column(String(50), default="")
    异地接受度 = Column(String(50), default="")

    # 理想对象
    理想对象年龄 = Column(String(50), default="")
    理想对象身高 = Column(String(50), default="")
    理想对象属性 = Column(String(50), default="")
    理想对象类型 = Column(String(200), default="")
    理想型描述 = Column(Text, default="")

    # 详细描述
    交友方式 = Column(Text, default="")
    个人特点 = Column(Text, default="")
    恋爱癖好 = Column(Text, default="")
    最重要因素 = Column(Text, default="")
    恋爱观念变化 = Column(Text, default="")
    恋爱历史 = Column(Text, default="")
    状态看法 = Column(Text, default="")
    最深刻经历 = Column(Text, default="")
    角色看法 = Column(Text, default="")
    理想伴侣关系 = Column(Text, default="")
    幸福感来源 = Column(Text, default="")
    其他想说的话 = Column(Text, default="")

    # 来源标记
    来源 = Column(String(30), default="线上互选")
    member_no = Column(String(20), default="")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
