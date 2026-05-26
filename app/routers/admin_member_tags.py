"""会员标签管理 API"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.cms import MemberTag, MemberProfileTag

router = APIRouter(prefix="/api/admin/member-tags", tags=["后台会员标签管理"])


# ==================== Schema ====================

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = "general"
    color: str = "#409EFF"
    sort_order: int = 0


class TagUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


# ==================== CRUD ====================

@router.get("")
def list_tags(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(MemberTag).order_by(MemberTag.sort_order, MemberTag.id).all()
    return items


@router.post("")
def create_tag(
    payload: TagCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    exists = db.query(MemberTag).filter(MemberTag.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=409, detail="标签名称已存在")
    obj = MemberTag(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{id}")
def update_tag(
    id: int,
    payload: TagUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = db.query(MemberTag).filter(MemberTag.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="标签不存在")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in updates:
        exists = db.query(MemberTag).filter(MemberTag.name == updates["name"], MemberTag.id != id).first()
        if exists:
            raise HTTPException(status_code=409, detail="标签名称已存在")
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_tag(
    id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = db.query(MemberTag).filter(MemberTag.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="标签不存在")
    # 同时删除所有关联
    db.query(MemberProfileTag).filter(MemberProfileTag.tag_id == id).delete()
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}


# ==================== 绑定/解绑 ====================

@router.post("/{tag_id}/bind/{member_id}")
def bind_tag(
    tag_id: int,
    member_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    tag = db.query(MemberTag).filter(MemberTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    # 检查会员是否存在
    from app.models.member_profile import MemberProfile
    member = db.query(MemberProfile).filter(MemberProfile.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 检查是否已绑定
    existing = db.query(MemberProfileTag).filter(
        MemberProfileTag.tag_id == tag_id,
        MemberProfileTag.member_id == member_id,
    ).first()
    if existing:
        return {"detail": "already_bound", "tag_id": tag_id, "member_id": member_id}

    obj = MemberProfileTag(tag_id=tag_id, member_id=member_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{tag_id}/unbind/{member_id}")
def unbind_tag(
    tag_id: int,
    member_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = db.query(MemberProfileTag).filter(
        MemberProfileTag.tag_id == tag_id,
        MemberProfileTag.member_id == member_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="未找到绑定关系")
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}
