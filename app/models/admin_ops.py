"""总后台运营中台模型：任务台、AI 调用成本、每日复盘。"""
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text

from app.core.database import Base


class OpsTask(Base):
    """私域/企微/朋友圈等运营任务。"""
    __tablename__ = "ops_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_date = Column(Date, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default="general", index=True)
    source = Column(String(50), default="manual", index=True)
    owner = Column(String(100), default="")
    status = Column(String(30), default="pending", index=True)  # pending/running/done/failed/skipped
    priority = Column(Integer, default=3)
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    detail = Column(Text, default="")
    result = Column(Text, default="")
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiUsageLog(Base):
    """AI 调用埋点：记录来源、模型、token、耗时、状态和成本估算。"""
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(80), default="unknown", index=True)
    scene = Column(String(120), default="", index=True)
    provider = Column(String(50), default="")
    model = Column(String(100), default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    estimated_cost_cny = Column(Numeric(12, 6), default=0)
    status = Column(String(30), default="success", index=True)  # success/fallback/error
    error_message = Column(Text, default="")
    request_preview = Column(Text, default="")
    response_preview = Column(Text, default="")
    meta_json = Column(Text, default="{}")


class OpsDailyReview(Base):
    """每日运营复盘。"""
    __tablename__ = "ops_daily_reviews"

    id = Column(Integer, primary_key=True, index=True)
    review_date = Column(Date, unique=True, index=True, nullable=False)
    status = Column(String(30), default="draft", index=True)  # draft/reviewed/archived
    summary = Column(Text, default="")
    wins = Column(Text, default="")
    risks = Column(Text, default="")
    next_actions = Column(Text, default="")
    ai_suggestion = Column(Text, default="")
    reviewed_by = Column(String(100), default="")
    reviewed_at = Column(DateTime, nullable=True)
    is_locked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
