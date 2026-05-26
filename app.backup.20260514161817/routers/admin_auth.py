"""
管理员认证 API
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_admin, verify_password, hash_password
from app.models.admin import AdminUser
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, AdminUserInfo, AdminAccountDetail, AdminAccountCreateRequest, AdminBindWechatRequest

router = APIRouter(prefix="/api/admin/auth", tags=["后台认证"])


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(401, "账号或密码错误")
    if not admin.is_active:
        raise HTTPException(403, "管理员账号已禁用")

    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": str(admin.id), "type": "admin", "role": admin.role})
    return AdminLoginResponse(
        token=token,
        user=AdminUserInfo(
            id=admin.id,
            username=admin.username,
            display_name=admin.display_name,
            role=admin.role,
            is_active=admin.is_active,
        )
    )


@router.get("/me", response_model=AdminUserInfo)
def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return AdminUserInfo(
        id=admin.id,
        username=admin.username,
        display_name=admin.display_name,
        role=admin.role,
        is_active=admin.is_active,
    )


def ensure_default_admin(db: Session):
    existing = db.query(AdminUser).filter(AdminUser.username == "admin").first()
    if existing:
        return
    admin = AdminUser(
        username="admin",
        password_hash=hash_password("admin123456"),
        display_name="系统管理员",
        role="super_admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()


# ====== 管理员账号管理 ======


@router.get("/admins", response_model=list[AdminAccountDetail])
def list_admins(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取管理员列表（仅 super_admin）"""
    if admin.role != "super_admin":
        raise HTTPException(403, "仅超级管理员可查看管理员列表")
    admins = db.query(AdminUser).order_by(AdminUser.id.asc()).all()
    return [
        AdminAccountDetail(
            id=a.id,
            username=a.username,
            display_name=a.display_name or "",
            role=a.role,
            is_active=a.is_active,
            wechat_openid=a.wechat_openid,
            last_login_at=a.last_login_at.isoformat() if a.last_login_at else None,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in admins
    ]


@router.post("/admins", status_code=201)
def create_admin(
    req: AdminAccountCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建管理员账号（仅 super_admin）"""
    if admin.role != "super_admin":
        raise HTTPException(403, "仅超级管理员可创建管理员账号")
    existing = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if existing:
        raise HTTPException(409, "用户名已存在")
    new_admin = AdminUser(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        role=req.role,
        is_active=True,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return AdminAccountDetail(
        id=new_admin.id,
        username=new_admin.username,
        display_name=new_admin.display_name or "",
        role=new_admin.role,
        is_active=new_admin.is_active,
        wechat_openid=None,
        last_login_at=None,
        created_at=new_admin.created_at.isoformat() if new_admin.created_at else None,
    )


@router.put("/admins/{admin_id}/toggle")
def toggle_admin(
    admin_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """启用/禁用管理员（仅 super_admin，不能禁用自己）"""
    if admin.role != "super_admin":
        raise HTTPException(403, "仅超级管理员可操作")
    if admin.id == admin_id:
        raise HTTPException(400, "不能禁用自己")
    target = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not target:
        raise HTTPException(404, "管理员不存在")
    target.is_active = not target.is_active
    db.commit()
    return {"id": target.id, "is_active": target.is_active, "message": "已启用" if target.is_active else "已禁用"}


@router.post("/bind-wechat")
def bind_wechat(
    req: AdminBindWechatRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """将当前管理员账号与微信小程序用户绑定（管理员在小程序发活动自动标记官方）"""
    existing = db.query(AdminUser).filter(AdminUser.wechat_openid == req.openid).first()
    if existing and existing.id != admin.id:
        raise HTTPException(409, "该微信用户已绑定其他管理员账号")
    admin.wechat_openid = req.openid
    db.commit()
    return {"message": f"已绑定微信用户 {req.openid[:8]}...", "wechat_openid": req.openid}
