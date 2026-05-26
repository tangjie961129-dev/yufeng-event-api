"""
恋爱服务数据库模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, DECIMAL
from datetime import datetime
from app.core.database import Base


class MatchCredit(Base):
    """用户匹配次数"""
    __tablename__ = "match_credits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    credits = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatchSession(Base):
    """AI匹配候选会话：进入企微/包间确认后才最终消耗次数"""
    __tablename__ = "match_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    candidate_member_id = Column(Integer, ForeignKey("member_profiles.id"), nullable=True, index=True)
    candidate_name_snapshot = Column(String(100), default="")
    match_type = Column(String(30), default="love", index=True)  # love/portrait
    status = Column(String(30), default="pending_room", index=True)  # pending_room/consume_pending/consumed/refunded/expired
    match_score = Column(DECIMAL(5, 2), default=0)
    score_breakdown_json = Column(Text, default="{}")
    reality_signals_json = Column(Text, default="[]")
    source_agent_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    referral_binding_id = Column(Integer, nullable=True, index=True)
    room_status = Column(String(30), default="not_created", index=True)
    room_external_id = Column(String(100), default="")
    credit_delta = Column(Integer, default=0)
    idempotency_key = Column(String(100), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    consumed_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    note = Column(Text, default="")


class MatchRoomInvitation(Base):
    """AI匹配三人包间/企微邀请记录"""
    __tablename__ = "match_room_invitations"

    id = Column(Integer, primary_key=True)
    match_session_id = Column(Integer, ForeignKey("match_sessions.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    candidate_member_id = Column(Integer, ForeignKey("member_profiles.id"), nullable=True, index=True)
    invitation_channel = Column(String(30), default="wecom", index=True)
    invitation_status = Column(String(30), default="pending", index=True)  # pending/sent/joined/expired/cancelled
    external_userid = Column(String(100), default="", index=True)
    share_link = Column(String(500), default="")
    share_message = Column(Text, default="")
    sent_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BoyfriendState(Base):
    """AI男友养成状态"""
    __tablename__ = "boyfriend_states"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String(100), default="你的AI男友")
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    max_exp = Column(Integer, default=100)
    affinity = Column(Integer, default=0)
    is_awake = Column(Boolean, default=True)
    personality = Column(String(50), default="温柔体贴")  # 温柔体贴/阳光活力/沉稳可靠
    last_action_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BoyfriendMessage(Base):
    """AI男友聊天消息"""
    __tablename__ = "boyfriend_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String(20))  # boyfriend/user
    content = Column(Text)
    action_type = Column(String(20))  # chat/feed/play/gift
    exp_gained = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
