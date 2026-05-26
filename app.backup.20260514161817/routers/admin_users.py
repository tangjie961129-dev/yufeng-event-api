"""
管理员用户 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy import or_, cast, String, func as sa_func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.user import User
from app.schemas.admin import AdminUserListItem, AdminUserListResponse

router = APIRouter(prefix="/api/admin/users", tags=["后台用户管理"])


@router.get("", response_model=AdminUserListResponse)
def list_users(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            User.phone.ilike(f"%{keyword}%"),
            cast(User.id, String).ilike(f"%{keyword}%")
        ))

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        AdminUserListItem(
            id=u.id,
            nickname=u.nickname or "",
            phone=u.phone or "",
            is_organizer=bool(u.is_organizer),
            organizer_verified=bool(u.organizer_verified),
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)
