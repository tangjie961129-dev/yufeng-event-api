"""
活动相关数据库模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, DECIMAL, BigInteger, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class Event(Base):
    """活动表"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(30), default="其他")
    cover_image = Column(String(500), default="")
    images = Column(Text, default="[]")  # JSON array of URLs
    registration_form = Column(Text, default="{}")  # JSON schema for signup form

    # 位置
    location_name = Column(String(200), default="")
    address = Column(String(300), default="")
    latitude = Column(DECIMAL(10, 7), nullable=True)
    longitude = Column(DECIMAL(10, 7), nullable=True)

    # 时间
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    registration_deadline = Column(DateTime(timezone=True), nullable=True)
    max_participants = Column(Integer, nullable=True)

    # 费用
    price = Column(DECIMAL(10, 2), default=0)  # 0=免费

    # 状态
    status = Column(
        String(20), default="pending",
        comment="draft/pending_review/published/rejected/cancelled/ended"
    )
    reject_reason = Column(Text, default="")

    publisher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 官方标记
    is_official = Column(Boolean, default=False, comment="是否为平台官方发布")

    # 统计
    view_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)


class EventRegistration(Base):
    """活动报名表"""
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(
        String(20), default="pending",
        comment="pending/paid/verified/cancelled/refunded"
    )
    ticket_code = Column(String(50), unique=True, nullable=True)
    quantity = Column(Integer, default=1)
    total_price = Column(DECIMAL(10, 2), default=0)

    # 支付
    payment_method = Column(String(20), default="")
    payment_id = Column(String(100), default="")       # 微信支付订单号
    prepay_id = Column(String(100), default="")        # 微信预支付ID
    paid_at = Column(DateTime(timezone=True), nullable=True)
    commission_rate = Column(DECIMAL(5, 2), default=0)  # 这笔订单的抽成比例
    commission_amount = Column(DECIMAL(10, 2), default=0)

    # 核销
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    remark = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 唯一约束：同一用户对同一活动只能报名一次
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user"),
    )


class EventFavorite(Base):
    """活动收藏表"""
    __tablename__ = "event_favorites"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_fav_event_user"),
    )


class EventReview(Base):
    """活动评价表"""
    __tablename__ = "event_reviews"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )


class OrganizerCertification(Base):
    """主办方资质认证表"""
    __tablename__ = "organizer_certifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    real_name = Column(String(50), default="")
    phone = Column(String(20), default="")
    id_card = Column(String(30), default="")
    qualification = Column(Text, default="[]")  # JSON array of image URLs
    intro = Column(Text, default="")  # 主办方介绍
    status = Column(String(20), default="pending")  # pending/approved/rejected
    reject_reason = Column(Text, default="")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommissionSetting(Base):
    """平台抽成配置表（单行配置）"""
    __tablename__ = "commission_settings"

    id = Column(Integer, primary_key=True, index=True)
    rate = Column(DECIMAL(5, 2), default=10.00)       # 百分比
    min_fee = Column(DECIMAL(10, 2), default=0)        # 最低抽成
    max_fee = Column(DECIMAL(10, 2), nullable=True)    # 最高抽成
    ui_config_json = Column(Text, default="")           # 装修/UI配置 JSON
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
