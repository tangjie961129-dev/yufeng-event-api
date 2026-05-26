"""私域数据统计 — 渠道主分销 + 引流点击汇总看板

路径: /api/admin/stats/private-domain
功能: 渠道主数量/填表/成交/佣金 + 引流点击 + 每日趋势
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.routers.partner_router import ChannelPartner, PartnerRegister, PartnerWithdraw
from app.routers.invite_router import InviteClick, CHANNEL_NAMES

router = APIRouter(prefix="/api/admin/stats", tags=["私域数据统计"])


@router.get("/private-domain")
def private_domain_stats(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """渠道主分销 + 引流点击综合数据"""
    today = date.today()
    since = today - timedelta(days=days)
    yesterday = today - timedelta(days=1)

    # ── 渠道主概览 ──
    total_partners = db.query(func.count(ChannelPartner.id)).scalar() or 0
    active_partners = db.query(func.count(ChannelPartner.id)).filter(
        ChannelPartner.status == "active"
    ).scalar() or 0
    new_partners_today = db.query(func.count(ChannelPartner.id)).filter(
        func.date(ChannelPartner.created_at) == today
    ).scalar() or 0

    # ── 填表统计 ──
    total_registers = db.query(func.count(PartnerRegister.id)).scalar() or 0
    confirmed_registers = db.query(func.count(PartnerRegister.id)).filter(
        PartnerRegister.status == "confirmed"
    ).scalar() or 0
    pending_registers = db.query(func.count(PartnerRegister.id)).filter(
        PartnerRegister.status == "pending"
    ).scalar() or 0
    today_registers = db.query(func.count(PartnerRegister.id)).filter(
        func.date(PartnerRegister.created_at) == today
    ).scalar() or 0
    yesterday_registers = db.query(func.count(PartnerRegister.id)).filter(
        func.date(PartnerRegister.created_at) == yesterday
    ).scalar() or 0

    # ── 佣金统计 ──
    total_commission = float(
        db.query(func.coalesce(func.sum(ChannelPartner.total_commission), 0))
        .scalar() or 0
    )
    total_withdrawable = float(
        db.query(func.coalesce(func.sum(ChannelPartner.withdrawable), 0))
        .scalar() or 0
    )

    # 昨日新增佣金（按 partner_registers 的 total_fee 统计）
    yesterday_commission = float(
        db.query(func.coalesce(func.sum(PartnerRegister.total_fee), 0))
        .filter(func.date(PartnerRegister.created_at) == yesterday)
        .scalar() or 0
    )
    today_commission = float(
        db.query(func.coalesce(func.sum(PartnerRegister.total_fee), 0))
        .filter(func.date(PartnerRegister.created_at) == today)
        .scalar() or 0
    )

    # ── 提现统计 ──
    total_withdrawn = float(
        db.query(func.coalesce(func.sum(PartnerWithdraw.amount), 0))
        .filter(PartnerWithdraw.status == "done")
        .scalar() or 0
    )
    pending_withdraws = db.query(func.count(PartnerWithdraw.id)).filter(
        PartnerWithdraw.status == "pending"
    ).scalar() or 0

    # ── 每日趋势（填表数 + 佣金） ──
    daily_stats = (
        db.query(
            func.date(PartnerRegister.created_at).label("day"),
            func.count(PartnerRegister.id).label("register_count"),
            func.coalesce(func.sum(PartnerRegister.total_fee), 0).label("commission"),
        )
        .filter(func.date(PartnerRegister.created_at) >= since)
        .group_by(func.date(PartnerRegister.created_at))
        .order_by(func.date(PartnerRegister.created_at).desc())
        .limit(days)
        .all()
    )

    daily = [
        {
            "day": str(d.day),
            "registers": d.register_count,
            "commission": float(d.commission),
        }
        for d in daily_stats
    ]

    # ── 渠道主排行（按佣金排序） ──
    partner_ranking = (
        db.query(
            ChannelPartner.name,
            ChannelPartner.partner_id,
            ChannelPartner.source,
            ChannelPartner.total_registers,
            ChannelPartner.total_deals,
            ChannelPartner.total_commission,
            ChannelPartner.withdrawable,
        )
        .filter(ChannelPartner.status == "active")
        .order_by(ChannelPartner.total_commission.desc())
        .limit(20)
        .all()
    )

    partners = [
        {
            "name": p.name or "未命名",
            "partner_id": p.partner_id,
            "source": p.source or "未知",
            "registers": p.total_registers,
            "deals": p.total_deals,
            "commission": float(p.total_commission),
            "withdrawable": float(p.withdrawable),
        }
        for p in partner_ranking
    ]

    # ── 引流点击统计 ──
    total_clicks = db.query(func.count(InviteClick.id)).scalar() or 0
    today_clicks = db.query(func.count(InviteClick.id)).filter(
        func.date(InviteClick.created_at) == today
    ).scalar() or 0

    # 按渠道分组
    channel_stats = (
        db.query(
            InviteClick.channel,
            func.count(InviteClick.id).label("total"),
            func.count(func.distinct(InviteClick.ip)).label("unique_ips"),
        )
        .filter(func.date(InviteClick.created_at) >= since)
        .group_by(InviteClick.channel)
        .order_by(func.count(InviteClick.id).desc())
        .all()
    )

    channels = [
        {
            "channel": c.channel,
            "name": CHANNEL_NAMES.get(c.channel, c.channel),
            "total": c.total,
            "unique_ips": c.unique_ips,
        }
        for c in channel_stats
    ]

    # 每日点击趋势
    daily_clicks = (
        db.query(
            func.date(InviteClick.created_at).label("day"),
            func.count(InviteClick.id).label("count"),
        )
        .filter(func.date(InviteClick.created_at) >= since)
        .group_by(func.date(InviteClick.created_at))
        .order_by(func.date(InviteClick.created_at).desc())
        .limit(days)
        .all()
    )

    click_daily = [
        {"day": str(d.day), "count": d.count} for d in daily_clicks
    ]

    # ── 最近填表记录 ──
    recent_registers = (
        db.query(
            PartnerRegister.customer_name,
            PartnerRegister.status,
            PartnerRegister.total_fee,
            PartnerRegister.created_at,
            ChannelPartner.name.label("partner_name"),
        )
        .join(ChannelPartner, PartnerRegister.partner_id == ChannelPartner.partner_id, isouter=True)
        .order_by(PartnerRegister.created_at.desc())
        .limit(20)
        .all()
    )

    recent = [
        {
            "customer": r.customer_name or "未命名",
            "status": r.status,
            "fee": float(r.total_fee),
            "date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            "partner": r.partner_name or "未知",
        }
        for r in recent_registers
    ]

    return {
        "overview": {
            "total_partners": total_partners,
            "active_partners": active_partners,
            "new_partners_today": new_partners_today,
            "total_registers": total_registers,
            "confirmed_registers": confirmed_registers,
            "pending_registers": pending_registers,
            "today_registers": today_registers,
            "yesterday_registers": yesterday_registers,
            "total_commission": round(total_commission, 2),
            "total_withdrawable": round(total_withdrawable, 2),
            "today_commission": round(today_commission, 2),
            "yesterday_commission": round(yesterday_commission, 2),
            "total_withdrawn": round(total_withdrawn, 2),
            "pending_withdraws": pending_withdraws,
            "total_clicks": total_clicks,
            "today_clicks": today_clicks,
        },
        "daily_trend": daily,
        "click_trend": click_daily,
        "channel_breakdown": channels,
        "partner_ranking": partners,
        "recent_activity": recent,
        "days": days,
    }
