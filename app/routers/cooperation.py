"""合作推广申请 API — 小程序提交 & 后台管理"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.admin import AdminUser
from app.models.cooperation import CooperationApplication
from app.models.user import User
from app.schemas import (
    CooperationApplyRequest,
    CooperationApplicationInfo,
    CooperationReviewRequest,
    CooperationNoteUpdate,
    CooperationFollowUpUpdate,
)

# ===== 小程序端（需登录）=====
user_router = APIRouter(prefix="/api/cooperation", tags=["合作推广申请-小程序端"])

# ===== 管理后台端 =====
admin_router = APIRouter(prefix="/api/admin/cooperations", tags=["合作推广申请-后台管理"])


def _app_to_info(obj: CooperationApplication) -> dict:
    """将 ORM 对象转为响应字典"""
    return {
        "id": obj.id,
        "user_id": obj.user_id,
        "name": obj.name or "",
        "phone": obj.phone or "",
        "wechat": obj.wechat or "",
        "resource_type": obj.resource_type or "",
        "resource_name": obj.resource_name or "",
        "resource_desc": obj.resource_desc or "",
        "followers": obj.followers or "",
        "coop_intent": obj.coop_intent or "",
        "status": obj.status or "pending",
        "admin_note": obj.admin_note or "",
        "follow_up_at": obj.follow_up_at.isoformat() if obj.follow_up_at else None,
        "follow_up_count": obj.follow_up_count or 0,
        "reviewed_by": obj.reviewed_by,
        "reviewed_at": obj.reviewed_at.isoformat() if obj.reviewed_at else None,
        "reject_reason": obj.reject_reason or "",
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


# =====================================================================
# 小程序端接口
# =====================================================================


@user_router.post("/apply", status_code=201)
def submit_cooperation_apply(
    req: CooperationApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """小程序用户提交合作推广申请"""
    app = CooperationApplication(
        user_id=current_user.id,
        name=req.name.strip(),
        phone=req.phone.strip(),
        wechat=req.wechat.strip(),
        resource_type=req.resource_type.strip(),
        resource_name=req.resource_name.strip(),
        resource_desc=req.resource_desc.strip(),
        followers=req.followers.strip(),
        coop_intent=req.coop_intent.strip(),
        status="pending",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {
        "message": "合作推广申请提交成功，我们会尽快审核",
        "id": app.id,
        "status": app.status,
    }


# =====================================================================
# 管理后台接口
# =====================================================================


@admin_router.get("")
def list_cooperations(
    status: str = Query("all"),
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员查看合作推广申请列表"""
    query = db.query(CooperationApplication)
    if status != "all":
        query = query.filter(CooperationApplication.status == status)
    if keyword:
        query = query.filter(or_(
            CooperationApplication.name.ilike(f"%{keyword}%"),
            CooperationApplication.phone.ilike(f"%{keyword}%"),
            CooperationApplication.wechat.ilike(f"%{keyword}%"),
            CooperationApplication.resource_name.ilike(f"%{keyword}%"),
            CooperationApplication.resource_type.ilike(f"%{keyword}%"),
            cast(CooperationApplication.id, String).ilike(f"%{keyword}%"),
        ))
    total = query.count()
    rows = query.order_by(CooperationApplication.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = [_app_to_info(app) for app in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/stats")
def coop_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """合作推广申请统计（各状态数量）"""
    from sqlalchemy import func as sa_func

    rows = db.query(
        CooperationApplication.status,
        sa_func.count(CooperationApplication.id)
    ).group_by(CooperationApplication.status).all()
    stats = {status: int(count) for status, count in rows}
    return {
        "pending": stats.get("pending", 0),
        "reviewing": stats.get("reviewing", 0),
        "approved": stats.get("approved", 0),
        "rejected": stats.get("rejected", 0),
        "closed": stats.get("closed", 0),
        "total": sum(stats.values()),
    }


@admin_router.get("/{app_id}")
def get_cooperation_detail(
    app_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员查看合作推广申请详情"""
    app = db.query(CooperationApplication).filter(CooperationApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "合作推广申请不存在")
    return _app_to_info(app)


@admin_router.post("/{app_id}/review")
def review_cooperation(
    app_id: int,
    req: CooperationReviewRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """审核合作推广申请：approve / reject / close"""
    app = db.query(CooperationApplication).filter(CooperationApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "合作推广申请不存在")

    now = datetime.now(timezone.utc)
    app.reviewed_by = admin.id
    app.reviewed_at = now

    if req.action == "approve":
        app.status = "approved"
        app.reject_reason = ""
    elif req.action == "reject":
        app.status = "rejected"
        app.reject_reason = req.reject_reason or "审核未通过"
    elif req.action == "close":
        app.status = "closed"
        app.reject_reason = req.reject_reason or ""
    else:
        raise HTTPException(400, f"不支持的操作: {req.action}")

    db.commit()
    return {"message": "ok", "id": app.id, "status": app.status}


@admin_router.put("/{app_id}/note")
def update_cooperation_note(
    app_id: int,
    req: CooperationNoteUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员更新申请备注"""
    app = db.query(CooperationApplication).filter(CooperationApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "合作推广申请不存在")
    app.admin_note = req.admin_note
    db.commit()
    return {"message": "备注已更新", "id": app.id}


@admin_router.post("/{app_id}/follow-up")
def follow_up_cooperation(
    app_id: int,
    req: CooperationFollowUpUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """记录跟进：更新跟进时间和跟进次数"""
    app = db.query(CooperationApplication).filter(CooperationApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "合作推广申请不存在")
    app.follow_up_at = req.follow_up_at or datetime.now(timezone.utc)
    app.follow_up_count = (app.follow_up_count or 0) + 1
    db.commit()
    return {
        "message": "跟进已记录",
        "id": app.id,
        "follow_up_at": app.follow_up_at.isoformat() if app.follow_up_at else None,
        "follow_up_count": app.follow_up_count,
    }
