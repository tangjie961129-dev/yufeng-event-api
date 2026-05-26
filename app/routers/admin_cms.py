"""内容中心(CMS) 管理端 API"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.cms import CmsCategory, CmsBanner, CmsPageWidget, CmsAnnouncement

router = APIRouter(prefix="/api/admin/cms", tags=["后台CMS管理"])


# ==================== CRUD 工具函数 ====================

def _get_or_404(db: Session, model, id: int, detail: str = "记录不存在"):
    obj = db.query(model).filter(model.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail=detail)
    return obj


# ==================== Request/Response Schema ====================

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    key: str = Field(..., min_length=1, max_length=100)
    icon: str = ""
    color: str = "#7c3aed"
    description: str = ""
    sort_order: int = 0
    is_enabled: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_enabled: Optional[bool] = None


class BannerCreate(BaseModel):
    title: str = ""
    subtitle: str = ""
    image_url: str = ""
    target_url: str = ""
    page: str = "home"
    sort_order: int = 0
    is_enabled: bool = True


class BannerUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    target_url: Optional[str] = None
    page: Optional[str] = None
    sort_order: Optional[int] = None
    is_enabled: Optional[bool] = None


class PageWidgetCreate(BaseModel):
    page: str = Field(..., min_length=1, max_length=50)
    widget_type: str = Field(..., min_length=1, max_length=50)
    config: dict = Field(default_factory=dict)
    sort_order: int = 0
    is_enabled: bool = True


class PageWidgetUpdate(BaseModel):
    page: Optional[str] = None
    widget_type: Optional[str] = None
    config: Optional[dict] = None
    sort_order: Optional[int] = None
    is_enabled: Optional[bool] = None


class AnnouncementCreate(BaseModel):
    title: str = ""
    content: str = ""
    link_url: str = ""
    is_published: bool = False
    sort_order: int = 0


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    link_url: Optional[str] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None


# ==================== 分类 ====================

@router.get("/categories")
def list_categories(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(CmsCategory).order_by(CmsCategory.sort_order, CmsCategory.id).all()
    return items


@router.post("/categories")
def create_category(
    payload: CategoryCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    exists = db.query(CmsCategory).filter(CmsCategory.key == payload.key).first()
    if exists:
        raise HTTPException(status_code=409, detail="分类标识 key 已存在")
    obj = CmsCategory(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/categories/{id}")
def update_category(
    id: int,
    payload: CategoryUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsCategory, id, "分类不存在")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "key" in updates:
        exists = db.query(CmsCategory).filter(CmsCategory.key == updates["key"], CmsCategory.id != id).first()
        if exists:
            raise HTTPException(status_code=409, detail="分类标识 key 已存在")
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/categories/{id}")
def delete_category(
    id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsCategory, id, "分类不存在")
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}


# ==================== Banner ====================

@router.get("/banners")
def list_banners(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CmsBanner).order_by(CmsBanner.sort_order, CmsBanner.id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/banners")
def create_banner(
    payload: BannerCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = CmsBanner(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/banners/{id}")
def update_banner(
    id: int,
    payload: BannerUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsBanner, id, "Banner不存在")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/banners/{id}")
def delete_banner(
    id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsBanner, id, "Banner不存在")
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}


# ==================== 页面组件 ====================

@router.get("/page-widgets")
def list_page_widgets(
    page: Optional[str] = Query(None, description="按页面过滤: home/love/test"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CmsPageWidget).order_by(CmsPageWidget.sort_order, CmsPageWidget.id)
    if page:
        query = query.filter(CmsPageWidget.page == page)
    return query.all()


@router.post("/page-widgets")
def create_page_widget(
    payload: PageWidgetCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = CmsPageWidget(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/page-widgets/{id}")
def update_page_widget(
    id: int,
    payload: PageWidgetUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsPageWidget, id, "页面组件不存在")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/page-widgets/{id}")
def delete_page_widget(
    id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsPageWidget, id, "页面组件不存在")
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}


# ==================== 公告 ====================

@router.get("/announcements")
def list_announcements(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(CmsAnnouncement).order_by(CmsAnnouncement.sort_order, CmsAnnouncement.id).all()
    return items


@router.post("/announcements")
def create_announcement(
    payload: AnnouncementCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = CmsAnnouncement(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/announcements/{id}")
def update_announcement(
    id: int,
    payload: AnnouncementUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsAnnouncement, id, "公告不存在")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for k, v in updates.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/announcements/{id}")
def delete_announcement(
    id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    obj = _get_or_404(db, CmsAnnouncement, id, "公告不存在")
    db.delete(obj)
    db.commit()
    return {"detail": "ok"}
