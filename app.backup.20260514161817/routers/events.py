"""
活动 CRUD API
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func as sa_func
from app.core.database import get_db
from app.core.security import get_current_user, get_optional_user
from app.models.user import User
from app.models.event import Event, EventRegistration, EventFavorite
from app.models.admin import AdminUser
from app.schemas import (
    EventCreate, EventUpdate, EventInfo, EventListItem, EventListResponse,
    PaginationParams, UserInfo, RegistrationFormSchema,
)

router = APIRouter(prefix="/api/events", tags=["活动管理"])


def _safe_json_loads(raw_value, fallback):
    if raw_value in (None, ""):
        return fallback
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _parse_registration_form(raw_value):
    data = _safe_json_loads(raw_value, {})
    if not isinstance(data, dict):
        data = {}
    return RegistrationFormSchema(**data)


@router.get("", response_model=EventListResponse)
def list_events(
    page: int = 1,
    page_size: int = 20,
    category: str = "",
    status: str = "published",
    keyword: str = "",
    latitude: float = None,
    longitude: float = None,
    sort: str = "start_time",
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    """获取活动列表（支持筛选 / 排序 / 附近）"""
    query = db.query(Event)

    # 默认只显示已发布的活动
    if status:
        query = query.filter(Event.status == status)
    if category:
        query = query.filter(Event.category == category)
    if keyword:
        query = query.filter(Event.title.ilike(f"%{keyword}%"))

    # 排序
    if sort == "start_time":
        query = query.order_by(Event.start_time.asc())
    elif sort == "newest":
        query = query.order_by(Event.created_at.desc())
    elif sort == "popular":
        query = query.order_by(Event.favorite_count.desc(), Event.view_count.desc())

    total = query.count()
    events = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取收藏状态
    fav_event_ids = set()
    if user:
        favs = db.query(EventFavorite.event_id).filter(
            EventFavorite.user_id == user.id,
            EventFavorite.event_id.in_([e.id for e in events]),
        ).all()
        fav_event_ids = {f[0] for f in favs}

    # 获取报名人数
    reg_counts = _get_reg_counts(db, [e.id for e in events])

    items = []
    for e in events:
        publisher = db.query(User).filter(User.id == e.publisher_id).first()
        items.append(EventListItem(
            id=e.id,
            title=e.title,
            category=e.category or "",
            cover_image=e.cover_image or "",
            location_name=e.location_name or "",
            start_time=e.start_time,
            price=float(e.price) if e.price else 0,
            status=e.status,
            max_participants=e.max_participants,
            registered_count=reg_counts.get(e.id, 0),
            publisher_nickname=publisher.nickname if publisher else "",
            publisher_avatar=publisher.avatar_url if publisher else "",
            registrant_count=reg_counts.get(e.id, 0),
            favorite_count=e.favorite_count or 0,
            is_favorited=e.id in fav_event_ids,
            is_official=bool(e.is_official),
        ))

    return EventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/my", response_model=EventListResponse)
def my_events(
    role: str = "publisher",  # publisher or participant
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我发布/参加的活动"""
    if role == "publisher":
        query = db.query(Event).filter(Event.publisher_id == user.id)
    else:
        regs = db.query(EventRegistration.event_id).filter(
            EventRegistration.user_id == user.id
        ).subquery()
        query = db.query(Event).filter(Event.id.in_(regs))

    total = query.count()
    events = query.order_by(Event.created_at.desc()) \
                  .offset((page - 1) * page_size).limit(page_size).all()

    fav_event_ids = set()
    favs = db.query(EventFavorite.event_id).filter(
        EventFavorite.user_id == user.id,
        EventFavorite.event_id.in_([e.id for e in events]),
    ).all()
    fav_event_ids = {f[0] for f in favs}
    reg_counts = _get_reg_counts(db, [e.id for e in events])

    items = []
    for e in events:
        publisher = db.query(User).filter(User.id == e.publisher_id).first()
        items.append(EventListItem(
            id=e.id,
            title=e.title,
            category=e.category or "",
            cover_image=e.cover_image or "",
            location_name=e.location_name or "",
            start_time=e.start_time,
            price=float(e.price) if e.price else 0,
            status=e.status,
            max_participants=e.max_participants,
            registered_count=reg_counts.get(e.id, 0),
            publisher_nickname=publisher.nickname if publisher else "",
            publisher_avatar=publisher.avatar_url if publisher else "",
            registrant_count=reg_counts.get(e.id, 0),
            favorite_count=e.favorite_count or 0,
            is_favorited=e.id in fav_event_ids,
            is_official=bool(e.is_official),
        ))
    return EventListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/template")
def get_event_template(user: User = Depends(get_current_user)):
    """主理人创建活动默认模板。"""
    return {
        "title": "周末轻社交活动",
        "category": "社交",
        "city": user.city or "广州",
        "venue": "屿风精选场地",
        "date": "本周六 19:30",
        "price": 99,
        "capacity": 24,
        "cover_hint": "建议使用真实现场图或质感生活方式图，避免廉价模板感。",
        "description": "适合想认识新朋友的彩虹伙伴，轻松、安全、有边界感。",
    }


@router.get("/form-config")
def get_event_form_config(user: User = Depends(get_current_user)):
    """活动报名表默认字段配置。"""
    return {
        "default_fields": [
            {"id": "name", "label": "称呼", "required": True, "enabled": True},
            {"id": "phone", "label": "手机号", "required": True, "enabled": True},
            {"id": "wechat", "label": "微信号", "required": True, "enabled": True},
            {"id": "city", "label": "所在城市", "required": False, "enabled": True},
        ],
        "custom_questions": [
            {"id": "q_first_time", "type": "single", "title": "是否第一次参加屿风活动？", "required": False},
            {"id": "q_expectation", "type": "text", "title": "你希望在活动中认识什么样的人？", "required": False},
        ],
    }


@router.get("/{event_id}", response_model=EventInfo)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    """获取活动详情"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")

    # 访问量 +1
    event.view_count = (event.view_count or 0) + 1
    db.commit()

    publisher = db.query(User).filter(User.id == event.publisher_id).first()

    # 收藏状态
    is_fav = False
    if user:
        fav = db.query(EventFavorite).filter(
            EventFavorite.event_id == event_id,
            EventFavorite.user_id == user.id,
        ).first()
        is_fav = fav is not None

    # 报名状态
    is_reg = False
    if user:
        reg = db.query(EventRegistration).filter(
            EventRegistration.event_id == event_id,
            EventRegistration.user_id == user.id,
        ).first()
        is_reg = reg is not None

    registrant_count = db.query(sa_func.count(EventRegistration.id)) \
        .filter(EventRegistration.event_id == event_id) \
        .filter(EventRegistration.status.in_(["paid", "verified"])) \
        .scalar() or 0

    images = _safe_json_loads(event.images, [])
    registration_form = _parse_registration_form(getattr(event, 'registration_form', '{}'))

    return EventInfo(
        id=event.id,
        title=event.title,
        description=event.description or "",
        category=event.category or "",
        cover_image=event.cover_image or "",
        images=images,
        registration_form=registration_form,
        location_name=event.location_name or "",
        address=event.address or "",
        latitude=float(event.latitude) if event.latitude else None,
        longitude=float(event.longitude) if event.longitude else None,
        start_time=event.start_time,
        end_time=event.end_time,
        registration_deadline=event.registration_deadline,
        max_participants=event.max_participants,
        price=float(event.price) if event.price else 0,
        status=event.status,
        publisher_id=event.publisher_id,
        publisher=UserInfo(
            id=publisher.id, nickname=publisher.nickname or "",
            avatar_url=publisher.avatar_url or "",
            is_organizer=publisher.is_organizer or False,
            organizer_verified=publisher.organizer_verified or False,
        ) if publisher else None,
        view_count=event.view_count or 0,
        favorite_count=event.favorite_count or 0,
        share_count=event.share_count or 0,
        is_favorited=is_fav,
        is_registered=is_reg,
        registrant_count=registrant_count,
        is_official=bool(event.is_official),
        created_at=event.created_at,
        published_at=event.published_at,
    )


@router.post("", response_model=EventInfo)
def create_event(
    req: EventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发布活动（必须是认证主办方，或绑定了微信的管理员）"""

    # 检查是否绑定了微信的管理员
    is_admin = db.query(AdminUser).filter(
        AdminUser.wechat_openid == user.openid,
        AdminUser.is_active == True,
    ).first() is not None

    if not is_admin and (not user.is_organizer or not user.organizer_verified):
        raise HTTPException(403, "只有认证主办方才能发布活动，请先提交主办方认证")

    registration_form_payload = req.registration_form.model_dump() if req.registration_form else {}
    event = Event(
        title=req.title,
        description=req.description,
        category=req.category or "其他",
        cover_image=req.cover_image or "",
        images=json.dumps(req.images, ensure_ascii=False),
        registration_form=json.dumps(registration_form_payload, ensure_ascii=False),
        location_name=req.location_name,
        address=req.address,
        latitude=req.latitude,
        longitude=req.longitude,
        start_time=req.start_time,
        end_time=req.end_time,
        registration_deadline=req.registration_deadline,
        max_participants=req.max_participants,
        price=req.price or 0,
        status="published" if is_admin else "pending_review",
        publisher_id=user.id,
        is_official=is_admin,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return get_event(event.id, db, user)


@router.put("/{event_id}", response_model=EventInfo)
def update_event(
    event_id: int,
    req: EventUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑活动（仅发布者或管理员）"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if event.publisher_id != user.id:
        raise HTTPException(403, "只有活动发布者才能编辑")

    update_data = req.model_dump(exclude_none=True)
    if "images" in update_data and update_data["images"] is not None:
        update_data["images"] = json.dumps(update_data["images"], ensure_ascii=False)
    if "registration_form" in update_data and update_data["registration_form"] is not None:
        update_data["registration_form"] = json.dumps(update_data["registration_form"], ensure_ascii=False)

    for key, value in update_data.items():
        setattr(event, key, value)

    # 编辑后重新进入审核
    if event.status == "published":
        event.status = "pending_review"

    db.commit()
    return get_event(event_id, db, user)


@router.post("/{event_id}/publish")
def publish_event(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发布活动（从草稿 -> 待审核）"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if event.publisher_id != user.id:
        raise HTTPException(403, "无权限")
    event.status = "pending_review"
    db.commit()
    return {"message": "活动已提交审核，请等待平台审核"}


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除活动（仅发布者，仅限草稿/已拒绝状态）"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if event.publisher_id != user.id:
        raise HTTPException(403, "无权限")
    if event.status not in ("draft", "rejected"):
        raise HTTPException(400, "只能删除草稿或已拒绝的活动")
    db.delete(event)
    db.commit()
    return {"message": "删除成功"}


# ====== 活动审核（管理员） ======

@router.post("/{event_id}/review")
def review_event(
    event_id: int,
    action: str = Query(..., pattern="^(approve|reject)$"),
    reject_reason: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核活动（管理员）"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")

    if action == "approve":
        event.status = "published"
        event.published_at = datetime.now(timezone.utc)
        event.reviewer_id = user.id
    else:
        event.status = "rejected"
        event.reject_reason = reject_reason
    db.commit()
    return {"message": "ok", "status": event.status}


# ====== 收藏 ======

@router.post("/{event_id}/favorite")
def toggle_favorite(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """收藏 / 取消收藏"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")

    fav = db.query(EventFavorite).filter(
        EventFavorite.event_id == event_id,
        EventFavorite.user_id == user.id,
    ).first()

    if fav:
        db.delete(fav)
        event.favorite_count = max(0, (event.favorite_count or 1) - 1)
        db.commit()
        return {"is_favorited": False, "favorite_count": event.favorite_count}
    else:
        fav = EventFavorite(event_id=event_id, user_id=user.id)
        db.add(fav)
        event.favorite_count = (event.favorite_count or 0) + 1
        db.commit()
        return {"is_favorited": True, "favorite_count": event.favorite_count}


@router.get("/my/favorites", response_model=EventListResponse)
def my_favorites(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的收藏列表"""
    fav_ids = db.query(EventFavorite.event_id).filter(
        EventFavorite.user_id == user.id
    ).order_by(EventFavorite.created_at.desc())
    total = fav_ids.count()

    events = db.query(Event).filter(
        Event.id.in_(fav_ids.subquery())
    ).order_by(Event.start_time.asc()) \
     .offset((page - 1) * page_size).limit(page_size).all()

    reg_counts = _get_reg_counts(db, [e.id for e in events])
    items = []
    for e in events:
        publisher = db.query(User).filter(User.id == e.publisher_id).first()
        items.append(EventListItem(
            id=e.id, title=e.title, category=e.category or "",
            cover_image=e.cover_image or "", location_name=e.location_name or "",
            start_time=e.start_time, price=float(e.price) if e.price else 0,
            status=e.status, max_participants=e.max_participants,
            registered_count=reg_counts.get(e.id, 0),
            publisher_nickname=publisher.nickname if publisher else "",
            publisher_avatar=publisher.avatar_url if publisher else "",
            registrant_count=reg_counts.get(e.id, 0),
            favorite_count=e.favorite_count or 0, is_favorited=True,
        ))
    return EventListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{event_id}/share")
def record_share(event_id: int, db: Session = Depends(get_db)):
    """记录转发次数"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event:
        event.share_count = (event.share_count or 0) + 1
        db.commit()
    return {"share_count": event.share_count if event else 0}


@router.get("/categories/list")
def list_categories(db: Session = Depends(get_db)):
    """获取活动分类列表"""
    result = db.query(Event.category).filter(
        Event.status == "published"
    ).distinct().all()
    categories = [r[0] for r in result if r[0]]
    return {"categories": categories or ["聚餐", "户外", "运动", "桌游", "K歌", "旅行", "读书", "其他"]}


# ====== 辅助函数 ======

def _get_reg_counts(db: Session, event_ids: list) -> dict:
    """批量获取各活动的报名人数"""
    if not event_ids:
        return {}
    from sqlalchemy import func
    rows = db.query(
        EventRegistration.event_id,
        func.count(EventRegistration.id)
    ).filter(
        EventRegistration.event_id.in_(event_ids),
        EventRegistration.status.in_(["paid", "verified"]),
    ).group_by(EventRegistration.event_id).all()
    return {r[0]: r[1] for r in rows}
