"""
管理员业务 API
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import or_, cast, String, func as sa_func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.user import User
from app.models.event import Event, EventRegistration, OrganizerCertification, CommissionSetting
from app.schemas import CertReviewRequest, CommissionConfig
from app.schemas.admin import AdminOrderItem, AdminOrderListResponse

router = APIRouter(prefix="/api/admin", tags=["后台业务管理"])


@router.get("/certs")
def list_certifications(
    status_filter: str = "pending",
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(OrganizerCertification, User).join(User, User.id == OrganizerCertification.user_id)
    if status_filter != "all":
        query = query.filter(OrganizerCertification.status == status_filter)
    if keyword:
        query = query.filter(or_(
            OrganizerCertification.real_name.ilike(f"%{keyword}%"),
            OrganizerCertification.phone.ilike(f"%{keyword}%"),
            User.nickname.ilike(f"%{keyword}%"),
            cast(OrganizerCertification.user_id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(OrganizerCertification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for cert, user in rows:
        try:
            qualification = json.loads(cert.qualification) if isinstance(cert.qualification, str) else (cert.qualification or [])
        except Exception:
            qualification = []
        items.append({
            "id": cert.id,
            "user_id": cert.user_id,
            "nickname": user.nickname or "",
            "avatar_url": user.avatar_url or "",
            "real_name": cert.real_name or "",
            "phone": cert.phone or "",
            "id_card": cert.id_card or "",
            "qualification": qualification,
            "intro": cert.intro or "",
            "status": cert.status or "pending",
            "reject_reason": cert.reject_reason or "",
            "created_at": cert.created_at.isoformat() if cert.created_at else None,
            "reviewed_at": cert.reviewed_at.isoformat() if cert.reviewed_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/certs/{cert_id}/review")
def review_certification(
    cert_id: int,
    req: CertReviewRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    cert = db.query(OrganizerCertification).filter(OrganizerCertification.id == cert_id).first()
    if not cert:
        raise HTTPException(404, "认证申请不存在")

    cert.reviewed_at = datetime.now(timezone.utc)
    cert.reviewed_by = None
    user = db.query(User).filter(User.id == cert.user_id).first()

    if req.action == "approve":
        cert.status = "approved"
        cert.reject_reason = ""
        if user:
            user.is_organizer = True
            user.organizer_verified = True
    else:
        cert.status = "rejected"
        cert.reject_reason = req.reject_reason or "审核未通过"
        if user:
            user.organizer_verified = False

    db.commit()
    return {"message": "ok", "status": cert.status}


@router.get("/commission", response_model=CommissionConfig)
def get_commission(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    setting = db.query(CommissionSetting).first()
    if not setting:
        return CommissionConfig(rate=10.0, min_fee=0, max_fee=None)
    return CommissionConfig(
        rate=float(setting.rate),
        min_fee=float(setting.min_fee) if setting.min_fee else 0,
        max_fee=float(setting.max_fee) if setting.max_fee else None,
    )


@router.post("/commission", response_model=CommissionConfig)
def update_commission(
    req: CommissionConfig,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    setting = db.query(CommissionSetting).first()
    if not setting:
        setting = CommissionSetting(rate=req.rate, min_fee=req.min_fee, max_fee=req.max_fee, updated_by=None)
        db.add(setting)
    else:
        setting.rate = req.rate
        setting.min_fee = req.min_fee
        setting.max_fee = req.max_fee
        setting.updated_by = None
        setting.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(setting)
    return CommissionConfig(
        rate=float(setting.rate),
        min_fee=float(setting.min_fee) if setting.min_fee else 0,
        max_fee=float(setting.max_fee) if setting.max_fee else None,
    )


@router.post("/events", status_code=201)
def admin_create_event(
    req: dict = Body(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员创建官方活动（跳过主办方认证检查，直接发布）"""
    title = req.get("title", "").strip()
    if not title:
        raise HTTPException(400, "活动标题不能为空")

    images = req.get("images", [])
    registration_form = req.get("registration_form", {})

    event = Event(
        title=title,
        description=req.get("description", ""),
        category=req.get("category", "其他"),
        cover_image=req.get("cover_image", ""),
        images=json.dumps(images, ensure_ascii=False) if images else "[]",
        registration_form=json.dumps(registration_form, ensure_ascii=False) if registration_form else "{}",
        location_name=req.get("location_name", ""),
        address=req.get("address", ""),
        latitude=req.get("latitude"),
        longitude=req.get("longitude"),
        start_time=datetime.fromisoformat(req["start_time"]) if isinstance(req.get("start_time"), str) else req.get("start_time"),
        end_time=datetime.fromisoformat(req["end_time"]) if isinstance(req.get("end_time"), str) else req.get("end_time"),
        registration_deadline=datetime.fromisoformat(req["registration_deadline"]) if isinstance(req.get("registration_deadline"), str) else req.get("registration_deadline"),
        max_participants=req.get("max_participants"),
        price=req.get("price", 0),
        status="published",
        publisher_id=admin.id,
        is_official=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "title": event.title,
        "status": event.status,
        "is_official": True,
        "message": "官方活动发布成功",
    }


@router.get("/events")
def list_events_for_admin(
    status_filter: str = "all",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    official_only: bool = False,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Event, User).join(User, User.id == Event.publisher_id)
    if status_filter != "all":
        query = query.filter(Event.status == status_filter)
    if official_only:
        query = query.filter(Event.is_official == True)
    if keyword:
        query = query.filter(or_(
            Event.title.ilike(f"%{keyword}%"),
            User.nickname.ilike(f"%{keyword}%"),
            cast(Event.id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(Event.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    event_ids = [event.id for event, _ in rows]
    reg_counts = dict(
        db.query(EventRegistration.event_id, sa_func.count(EventRegistration.id))
        .filter(EventRegistration.event_id.in_(event_ids) if event_ids else False)
        .group_by(EventRegistration.event_id)
        .all()
    ) if event_ids else {}
    items = []
    for event, user in rows:
        items.append({
            "id": event.id,
            "title": event.title,
            "category": event.category or "",
            "status": event.status,
            "price": float(event.price) if event.price else 0,
            "publisher_id": event.publisher_id,
            "publisher_nickname": user.nickname or "",
            "location_name": event.location_name or "",
            "start_time": event.start_time.isoformat() if event.start_time else None,
            "registrant_count": int(reg_counts.get(event.id, 0)),
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "reject_reason": event.reject_reason or "",
            "is_official": bool(event.is_official),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/events/{event_id}/review")
def review_event(
    event_id: int,
    action: str = Query(..., pattern="^(approve|reject)$"),
    reject_reason: str = "",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if action == "approve":
        event.status = "published"
        event.reject_reason = ""
        event.published_at = datetime.now(timezone.utc)
        event.reviewer_id = None
    else:
        event.status = "rejected"
        event.reject_reason = reject_reason or "审核未通过"
    db.commit()
    return {"message": "ok", "status": event.status}


@router.get("/orders", response_model=AdminOrderListResponse)
def list_orders(
    status_filter: str = "all",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(EventRegistration, Event, User).join(Event, Event.id == EventRegistration.event_id).join(User, User.id == EventRegistration.user_id)
    if status_filter != "all":
        query = query.filter(EventRegistration.status == status_filter)
    if keyword:
        query = query.filter(or_(
            Event.title.ilike(f"%{keyword}%"),
            User.nickname.ilike(f"%{keyword}%"),
            EventRegistration.payment_id.ilike(f"%{keyword}%"),
            cast(EventRegistration.id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(EventRegistration.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    publisher_ids = list({event.publisher_id for _, event, _ in rows})
    publisher_map = {u.id: u for u in db.query(User).filter(User.id.in_(publisher_ids)).all()} if publisher_ids else {}
    items = []
    for reg, event, user in rows:
        organizer = publisher_map.get(event.publisher_id)
        items.append(AdminOrderItem(
            id=reg.id,
            event_id=event.id,
            event_title=event.title or "",
            user_id=user.id,
            user_nickname=user.nickname or "",
            organizer_id=event.publisher_id,
            organizer_name=(organizer.nickname if organizer else ""),
            status=reg.status or "pending",
            quantity=reg.quantity or 0,
            total_price=float(reg.total_price) if reg.total_price else 0,
            payment_method=reg.payment_method or "",
            payment_id=reg.payment_id or "",
            commission_rate=float(reg.commission_rate) if reg.commission_rate else 0,
            commission_amount=float(reg.commission_amount) if reg.commission_amount else 0,
            paid_at=reg.paid_at.isoformat() if reg.paid_at else None,
            created_at=reg.created_at.isoformat() if reg.created_at else None,
        ))
    return AdminOrderListResponse(items=items, total=total, page=page, page_size=page_size)
