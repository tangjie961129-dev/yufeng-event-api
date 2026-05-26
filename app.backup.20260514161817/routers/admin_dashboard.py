"""
管理员仪表盘 API
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.user import User
from app.models.event import Event, EventRegistration, OrganizerCertification
from app.schemas.admin import DashboardOverview, DashboardTrendResponse, TrendItem

router = APIRouter(prefix="/api/admin/dashboard", tags=["后台仪表盘"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(sa_func.count(User.id)).scalar() or 0
    total_organizers = db.query(sa_func.count(User.id)).filter(User.organizer_verified == True).scalar() or 0
    total_events = db.query(sa_func.count(Event.id)).scalar() or 0
    pending_events = db.query(sa_func.count(Event.id)).filter(Event.status == "pending_review").scalar() or 0
    pending_certs = db.query(sa_func.count(OrganizerCertification.id)).filter(OrganizerCertification.status == "pending").scalar() or 0
    total_registrations = db.query(sa_func.count(EventRegistration.id)).scalar() or 0
    paid_orders = db.query(sa_func.count(EventRegistration.id)).filter(EventRegistration.status.in_(["paid", "verified"])).scalar() or 0
    total_revenue = db.query(sa_func.coalesce(sa_func.sum(EventRegistration.total_price), 0)).filter(EventRegistration.status.in_(["paid", "verified"])).scalar() or 0
    total_commission = db.query(sa_func.coalesce(sa_func.sum(EventRegistration.commission_amount), 0)).filter(EventRegistration.status.in_(["paid", "verified"])).scalar() or 0

    return DashboardOverview(
        total_users=int(total_users),
        total_organizers=int(total_organizers),
        total_events=int(total_events),
        pending_events=int(pending_events),
        pending_certs=int(pending_certs),
        total_registrations=int(total_registrations),
        paid_orders=int(paid_orders),
        total_revenue=float(total_revenue),
        total_commission=float(total_commission),
    )


@router.get("/trends", response_model=DashboardTrendResponse)
def dashboard_trends(
    days: int = 7,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    rows = db.query(
        sa_func.date(EventRegistration.created_at).label("d"),
        sa_func.count(EventRegistration.id),
        sa_func.coalesce(sa_func.sum(EventRegistration.total_price), 0),
    ).filter(
        EventRegistration.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    ).group_by(sa_func.date(EventRegistration.created_at)).all()

    row_map = {str(r[0]): r for r in rows}
    items = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        key = str(day)
        row = row_map.get(key)
        items.append(TrendItem(
            date=key,
            registrations=int(row[1]) if row else 0,
            revenue=float(row[2]) if row else 0.0,
        ))
    return DashboardTrendResponse(items=items)
