"""
报名 / 支付 / 验券 API
"""
from decimal import Decimal, ROUND_HALF_UP
import random
import string
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.event import Event, EventRegistration, CommissionSetting
from app.schemas import RegisterRequest, RegistrationInfo, TicketInfo, PaginatedResponse
from app.services.wechat_pay import (
    WechatPayAPIError,
    WechatPayConfigError,
    build_request_payment_params,
    create_jsapi_prepay,
    decrypt_notify_resource,
)

router = APIRouter(prefix="/api", tags=["报名 & 支付 & 验券"])


# ====== 报名 ======

@router.post("/events/{event_id}/register", response_model=RegistrationInfo)
def register_event(
    event_id: int,
    req: RegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """报名活动"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if event.status != "published":
        raise HTTPException(400, "活动未发布或已结束")

    # 检查是否已报名
    existing = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == user.id,
    ).first()
    if existing:
        if existing.status in ("paid", "verified"):
            raise HTTPException(400, "您已报名该活动")
        # pending/cancelled - 允许重新报名
        existing.status = "pending"
        existing.quantity = req.quantity
        existing.total_price = float(event.price or 0) * req.quantity
        existing.remark = req.remark
        existing.created_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return _reg_to_info(existing, event.title)

    # 检查名额
    if event.max_participants:
        reg_count = db.query(sa_func.count(EventRegistration.id)).filter(
            EventRegistration.event_id == event_id,
            EventRegistration.status.in_(["paid", "verified"]),
        ).scalar() or 0
        if reg_count + req.quantity > event.max_participants:
            raise HTTPException(400, "名额已满")

    # 检查截止时间
    if event.registration_deadline and datetime.now(timezone.utc) > event.registration_deadline:
        raise HTTPException(400, "报名已截止")

    total_price = float(event.price or 0) * req.quantity

    reg = EventRegistration(
        event_id=event_id,
        user_id=user.id,
        status="pending",
        quantity=req.quantity,
        total_price=total_price,
        remark=req.remark,
        ticket_code=_generate_ticket_code(),
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return _reg_to_info(reg, event.title)


@router.get("/my/registrations", response_model=PaginatedResponse)
def my_registrations(
    status_filter: str = "",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的报名列表"""
    query = db.query(EventRegistration).filter(
        EventRegistration.user_id == user.id
    )
    if status_filter:
        query = query.filter(EventRegistration.status == status_filter)

    total = query.count()
    regs = query.order_by(EventRegistration.created_at.desc()) \
                 .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for r in regs:
        event = db.query(Event).filter(Event.id == r.event_id).first()
        items.append(_reg_to_info(r, event.title if event else ""))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/events/{event_id}/registrations", response_model=PaginatedResponse)
def event_registrations(
    event_id: int,
    status_filter: str = "",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查看活动报名列表（仅主办方）"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")
    if event.publisher_id != user.id:
        raise HTTPException(403, "只有活动主办方才能查看报名列表")

    query = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id
    )
    if status_filter:
        query = query.filter(EventRegistration.status == status_filter)

    total = query.count()
    regs = query.order_by(EventRegistration.created_at.desc()) \
                 .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for r in regs:
        participant = db.query(User).filter(User.id == r.user_id).first()
        items.append({
            "id": r.id,
            "user_id": r.user_id,
            "nickname": participant.nickname if participant else "",
            "avatar_url": participant.avatar_url if participant else "",
            "status": r.status,
            "ticket_code": r.ticket_code,
            "quantity": r.quantity,
            "total_price": float(r.total_price) if r.total_price else 0,
            "paid_at": r.paid_at,
            "verified_at": r.verified_at,
            "remark": r.remark,
            "created_at": r.created_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ====== 支付 ======

@router.post("/events/{event_id}/pay")
async def create_payment(
    event_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建微信支付 JSAPI 订单，返回 wx.requestPayment 参数。"""
    body = await request.json()
    registration_id = body.get("registration_id")
    if not registration_id:
        raise HTTPException(422, "缺少报名记录 registration_id")

    reg = db.query(EventRegistration).filter(
        EventRegistration.id == registration_id,
        EventRegistration.user_id == user.id,
        EventRegistration.event_id == event_id,
    ).first()
    if not reg:
        raise HTTPException(404, "报名记录不存在")
    if reg.status == "paid":
        if reg.prepay_id:
            return build_request_payment_params(reg.prepay_id)
        raise HTTPException(400, "订单已支付")
    if reg.status != "pending":
        raise HTTPException(400, f"当前报名状态不允许支付: {reg.status}")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "活动不存在")

    total_amount = Decimal(str(reg.total_price or 0))
    if total_amount <= 0:
        reg.status = "paid"
        reg.payment_method = "free"
        reg.payment_id = f"FREE{reg.id}"
        reg.paid_at = datetime.now(timezone.utc)
        db.commit()
        return {"paid": True, "message": "免费活动已完成报名"}

    amount_total = int((total_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    out_trade_no = reg.payment_id or f"YF{reg.id}{datetime.now().strftime('%Y%m%d%H%M%S')}"

    commission = db.query(CommissionSetting).first()
    rate = float(commission.rate) / 100 if commission else 0.10
    commission_amount = total_amount * Decimal(str(rate))

    try:
        prepay = await create_jsapi_prepay(
            out_trade_no=out_trade_no,
            description=event.title or "屿风活动报名",
            amount_total=amount_total,
            payer_openid=user.openid,
            attach=f"event_id={event_id};registration_id={reg.id}",
        )
        prepay_id = prepay.get("prepay_id")
        pay_params = build_request_payment_params(prepay_id)
    except WechatPayConfigError as exc:
        raise HTTPException(500, f"微信支付配置未完成：{exc}") from exc
    except WechatPayAPIError as exc:
        raise HTTPException(502, str(exc)) from exc

    reg.payment_method = "wechat_pay"
    reg.prepay_id = prepay_id
    reg.payment_id = out_trade_no
    reg.commission_rate = float(commission.rate) if commission else 10.0
    reg.commission_amount = commission_amount
    db.commit()

    return pay_params


@router.post("/payment/notify")
async def payment_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付 v3 回调通知。"""
    payload = await request.json()
    resource = payload.get("resource") or {}
    try:
        data = decrypt_notify_resource(resource)
    except WechatPayConfigError as exc:
        raise HTTPException(400, str(exc)) from exc

    out_trade_no = data.get("out_trade_no") or ""
    transaction_id = data.get("transaction_id") or ""
    trade_state = data.get("trade_state") or ""

    if not out_trade_no:
        return {"code": "SUCCESS", "message": "ignored"}

    if trade_state != "SUCCESS":
        return {"code": "SUCCESS", "message": "ignored"}

    # 处理 MATCH 订单（购买匹配次数）
    if out_trade_no.startswith("MATCH"):
        if not transaction_id:
            return {"code": "SUCCESS", "message": "ignored"}
        # 从 out_trade_no 解析 user_id: MATCH{user_id}{timestamp}
        match_id_str = ""
        for ch in out_trade_no[5:]:
            if ch.isdigit():
                match_id_str += ch
            else:
                break
        if match_id_str:
            user = db.query(User).filter(User.id == int(match_id_str)).first()
            if user:
                user.match_credits = (user.match_credits or 0) + 3  # 买1次得3次
                db.commit()
        return {"code": "SUCCESS", "message": "OK"}

    reg = db.query(EventRegistration).filter(EventRegistration.payment_id == out_trade_no).first()
    if reg and trade_state == "SUCCESS" and reg.status == "pending":
        reg.status = "paid"
        reg.payment_method = "wechat_pay"
        if transaction_id:
            reg.prepay_id = reg.prepay_id or transaction_id
        reg.paid_at = datetime.now(timezone.utc)
        db.commit()

    return {"code": "SUCCESS", "message": "OK"}


# ====== 验券 ======

@router.get("/tickets/{ticket_code}", response_model=TicketInfo)
def query_ticket(
    ticket_code: str,
    db: Session = Depends(get_db),
):
    """查询核销码信息"""
    reg = db.query(EventRegistration).filter(
        EventRegistration.ticket_code == ticket_code
    ).first()
    if not reg:
        raise HTTPException(404, "核销码不存在")

    event = db.query(Event).filter(Event.id == reg.event_id).first()
    user = db.query(User).filter(User.id == reg.user_id).first()

    return TicketInfo(
        registration_id=reg.id,
        event_id=reg.event_id,
        event_title=event.title if event else "",
        event_start_time=event.start_time if event else datetime.now(),
        event_location=event.location_name or event.address or "",
        user_id=reg.user_id,
        user_nickname=user.nickname if user else "",
        status=reg.status,
        ticket_code=reg.ticket_code or "",
        quantity=reg.quantity,
        payment_id=reg.payment_id or "",
        created_at=reg.created_at,
    )


@router.post("/tickets/{ticket_code}/verify")
def verify_ticket(
    ticket_code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """核销验券（仅主办方）"""
    reg = db.query(EventRegistration).filter(
        EventRegistration.ticket_code == ticket_code
    ).first()
    if not reg:
        raise HTTPException(404, "核销码不存在")

    event = db.query(Event).filter(Event.id == reg.event_id).first()
    if not event or event.publisher_id != user.id:
        raise HTTPException(403, "只有活动主办方才能核销")

    if reg.status != "paid":
        raise HTTPException(400, f"当前状态不可核销: {reg.status}")

    reg.status = "verified"
    reg.verified_at = datetime.now(timezone.utc)
    reg.verified_by = user.id
    db.commit()

    return {
        "message": "核销成功",
        "user_nickname": db.query(User).filter(User.id == reg.user_id).first().nickname,
        "quantity": reg.quantity,
        "verified_at": reg.verified_at.isoformat(),
    }


@router.post("/events/{event_id}/cancel-registration")
def cancel_registration(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消报名（仅限未核销的）"""
    reg = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == user.id,
        EventRegistration.status.in_(["pending", "paid"]),
    ).first()
    if not reg:
        raise HTTPException(404, "未找到可取消的报名记录")

    reg.status = "cancelled"
    db.commit()
    return {"message": "已取消报名"}


# ====== 辅助函数 ======

def _generate_ticket_code() -> str:
    """生成唯一核销码"""
    chars = string.ascii_uppercase + string.digits
    return "YF" + "".join(random.choices(chars, k=10))


def _reg_to_info(reg: EventRegistration, event_title: str) -> RegistrationInfo:
    return RegistrationInfo(
        id=reg.id,
        event_id=reg.event_id,
        event_title=event_title,
        status=reg.status,
        ticket_code=reg.ticket_code,
        quantity=reg.quantity,
        total_price=float(reg.total_price) if reg.total_price else 0,
        payment_id=reg.payment_id or "",
        paid_at=reg.paid_at,
        verified_at=reg.verified_at,
        remark=reg.remark or "",
        created_at=reg.created_at,
    )
