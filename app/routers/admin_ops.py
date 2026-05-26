"""总后台 P0 运营中台 API。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.admin_ops import AiUsageLog, OpsDailyReview, OpsTask

router = APIRouter(prefix="/api/admin/ops", tags=["总后台运营中台"])


class OpsTaskCreate(BaseModel):
    task_date: date = Field(default_factory=date.today)
    title: str = Field(..., min_length=1, max_length=200)
    category: str = "general"
    source: str = "manual"
    owner: str = ""
    status: str = "pending"
    priority: int = 3
    scheduled_at: Optional[datetime] = None
    detail: str = ""


class OpsTaskUpdate(BaseModel):
    task_date: Optional[date] = None
    title: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    detail: Optional[str] = None
    result: Optional[str] = None


class DailyReviewUpsert(BaseModel):
    review_date: date = Field(default_factory=date.today)
    status: str = "draft"
    summary: str = ""
    wins: str = ""
    risks: str = ""
    next_actions: str = ""
    ai_suggestion: str = ""
    is_locked: bool = False


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _task_item(obj: OpsTask) -> dict:
    return {
        "id": obj.id,
        "task_date": str(obj.task_date),
        "title": obj.title,
        "category": obj.category,
        "source": obj.source,
        "owner": obj.owner,
        "status": obj.status,
        "priority": obj.priority,
        "scheduled_at": _dt(obj.scheduled_at),
        "completed_at": _dt(obj.completed_at),
        "detail": obj.detail or "",
        "result": obj.result or "",
        "created_at": _dt(obj.created_at),
        "updated_at": _dt(obj.updated_at),
    }


def _review_item(obj: OpsDailyReview) -> dict:
    return {
        "id": obj.id,
        "review_date": str(obj.review_date),
        "status": obj.status,
        "summary": obj.summary or "",
        "wins": obj.wins or "",
        "risks": obj.risks or "",
        "next_actions": obj.next_actions or "",
        "ai_suggestion": obj.ai_suggestion or "",
        "reviewed_by": obj.reviewed_by or "",
        "reviewed_at": _dt(obj.reviewed_at),
        "is_locked": bool(obj.is_locked),
        "created_at": _dt(obj.created_at),
        "updated_at": _dt(obj.updated_at),
    }


def _usage_item(obj: AiUsageLog) -> dict:
    return {
        "id": obj.id,
        "occurred_at": _dt(obj.occurred_at),
        "source": obj.source,
        "scene": obj.scene,
        "provider": obj.provider,
        "model": obj.model,
        "prompt_tokens": obj.prompt_tokens or 0,
        "completion_tokens": obj.completion_tokens or 0,
        "total_tokens": obj.total_tokens or 0,
        "latency_ms": obj.latency_ms or 0,
        "estimated_cost_cny": float(obj.estimated_cost_cny or 0),
        "status": obj.status,
        "error_message": obj.error_message or "",
        "request_preview": obj.request_preview or "",
        "response_preview": obj.response_preview or "",
    }


def ensure_today_seed_tasks(db: Session, target_date: date) -> None:
    """如果当天没有运营任务，生成 P0 默认任务骨架。"""
    exists = db.query(OpsTask.id).filter(OpsTask.task_date == target_date).first()
    if exists:
        return
    defaults = [
        ("02:00", "预生成今日朋友圈内容", "moments", "cron", "3条会员推荐 + 1条彩虹交友 tips，检查文案与配图是否齐全"),
        ("10:00", "缺图补救检查", "moments", "cron", "只补缺失配图，不重跑文案"),
        ("10:55", "上午朋友圈推送窗口", "moments", "cron", "推送前人工扫一眼是否有明显违和"),
        ("全天", "企微客服大脑回复辅助", "wecom", "system", "员工转发客户问题后，秒回+异步深度回复"),
        ("21:00", "当日运营复盘", "review", "manual", "复盘客服问题、朋友圈素材、AI成本和明日动作"),
    ]
    for hhmm, title, category, source, detail in defaults:
        scheduled_at = None
        if ":" in hhmm:
            hour, minute = [int(x) for x in hhmm.split(":", 1)]
            scheduled_at = datetime.combine(target_date, time(hour=hour, minute=minute))
        db.add(OpsTask(
            task_date=target_date,
            title=title,
            category=category,
            source=source,
            status="pending",
            priority=2 if category in {"moments", "wecom"} else 3,
            scheduled_at=scheduled_at,
            detail=detail,
        ))
    db.commit()


@router.get("/overview")
def ops_overview(
    day: date = Query(default_factory=date.today),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_today_seed_tasks(db, day)
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)

    task_rows = db.query(OpsTask.status, sa_func.count(OpsTask.id)).filter(OpsTask.task_date == day).group_by(OpsTask.status).all()
    task_stats = {status: int(count) for status, count in task_rows}
    usage_count = db.query(sa_func.count(AiUsageLog.id)).filter(AiUsageLog.occurred_at >= day_start, AiUsageLog.occurred_at < day_end).scalar() or 0
    token_sum = db.query(sa_func.coalesce(sa_func.sum(AiUsageLog.total_tokens), 0)).filter(AiUsageLog.occurred_at >= day_start, AiUsageLog.occurred_at < day_end).scalar() or 0
    cost_sum = db.query(sa_func.coalesce(sa_func.sum(AiUsageLog.estimated_cost_cny), Decimal("0"))).filter(AiUsageLog.occurred_at >= day_start, AiUsageLog.occurred_at < day_end).scalar() or Decimal("0")
    review = db.query(OpsDailyReview).filter(OpsDailyReview.review_date == day).first()

    return {
        "date": str(day),
        "task_stats": task_stats,
        "pending_tasks": task_stats.get("pending", 0) + task_stats.get("running", 0),
        "done_tasks": task_stats.get("done", 0),
        "ai_usage_count": int(usage_count),
        "ai_total_tokens": int(token_sum),
        "ai_estimated_cost_cny": float(cost_sum or 0),
        "review_status": review.status if review else "missing",
    }


@router.get("/tasks")
def list_tasks(
    day: date = Query(default_factory=date.today),
    status: str = "",
    category: str = "",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_today_seed_tasks(db, day)
    q = db.query(OpsTask).filter(OpsTask.task_date == day)
    if status:
        q = q.filter(OpsTask.status == status)
    if category:
        q = q.filter(OpsTask.category == category)
    items = q.order_by(OpsTask.scheduled_at.is_(None), OpsTask.scheduled_at, OpsTask.priority, OpsTask.id).all()
    return {"items": [_task_item(x) for x in items]}


@router.post("/tasks")
def create_task(payload: OpsTaskCreate, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    obj = OpsTask(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _task_item(obj)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, payload: OpsTaskUpdate, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    obj = db.query(OpsTask).filter(OpsTask.id == task_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="运营任务不存在")
    updates = payload.model_dump(exclude_unset=True)
    old_status = obj.status
    for key, value in updates.items():
        setattr(obj, key, value)
    if obj.status == "done" and old_status != "done" and not obj.completed_at:
        obj.completed_at = datetime.utcnow()
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return _task_item(obj)


@router.get("/ai-usage")
def list_ai_usage(
    day: date = Query(default_factory=date.today),
    source: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)
    q = db.query(AiUsageLog).filter(AiUsageLog.occurred_at >= day_start, AiUsageLog.occurred_at < day_end)
    if source:
        q = q.filter(AiUsageLog.source == source)
    total = q.count()
    items = q.order_by(AiUsageLog.occurred_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_usage_item(x) for x in items], "total": total, "page": page, "page_size": page_size}


@router.get("/daily-review")
def get_daily_review(day: date = Query(default_factory=date.today), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    review = db.query(OpsDailyReview).filter(OpsDailyReview.review_date == day).first()
    if not review:
        review = OpsDailyReview(review_date=day, status="draft")
        db.add(review)
        db.commit()
        db.refresh(review)
    return _review_item(review)


@router.put("/daily-review")
def upsert_daily_review(payload: DailyReviewUpsert, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    obj = db.query(OpsDailyReview).filter(OpsDailyReview.review_date == payload.review_date).first()
    if obj and obj.is_locked and payload.is_locked:
        raise HTTPException(status_code=409, detail="复盘已锁定，不能重复提交")
    if not obj:
        obj = OpsDailyReview(review_date=payload.review_date)
        db.add(obj)
    for key, value in payload.model_dump(exclude={"review_date"}).items():
        setattr(obj, key, value)
    if payload.status == "reviewed" or payload.is_locked:
        obj.reviewed_by = admin.display_name or admin.username
        obj.reviewed_at = datetime.utcnow()
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return _review_item(obj)
