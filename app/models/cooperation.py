"""合作推广申请数据库模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from app.core.database import Base


class CooperationApplication(Base):
    """合作推广申请"""
    __tablename__ = "cooperation_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="申请用户ID（小程序登录用户）")

    # 申请人信息
    name = Column(String(100), nullable=False, comment="联系人姓名")
    phone = Column(String(20), nullable=False, comment="手机号")
    wechat = Column(String(100), default="", comment="微信号")

    # 合作资源信息
    resource_type = Column(String(100), default="", comment="资源类型：公众号/小红书/抖音/社群/其他")
    resource_name = Column(String(200), default="", comment="资源名称/账号名")
    resource_desc = Column(Text, default="", comment="资源描述/简介")
    followers = Column(String(50), default="", comment="粉丝/订阅人数")

    # 合作意向
    coop_intent = Column(Text, default="", comment="合作意向说明")

    # 状态管理
    status = Column(String(30), default="pending", index=True, comment="pending:待审核, reviewing:审核中, approved:已通过, rejected:已驳回, closed:已关闭")
    admin_note = Column(Text, default="", comment="管理员备注")
    follow_up_at = Column(DateTime, nullable=True, comment="下次跟进时间")
    follow_up_count = Column(Integer, default=0, comment="跟进次数")

    # 审核信息
    reviewed_by = Column(Integer, nullable=True, comment="审核管理员ID")
    reviewed_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, default="", comment="驳回原因")

    # 时间
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
