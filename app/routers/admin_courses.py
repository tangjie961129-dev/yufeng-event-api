"""
课程管理后台 API
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.course import Course

router = APIRouter(prefix="/api/admin/love/courses", tags=["后台课程管理"])


class CourseCreate(BaseModel):
    title: str
    subtitle: str = ""
    description: str = ""
    cover_url: str = ""
    category: str = ""
    price: float = 0.0
    duration: str = ""
    lesson_count: int = 0
    student_count: int = 0
    instructor: str = ""
    is_published: bool = False
    sort_order: int = 0


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[str] = None
    lesson_count: Optional[int] = None
    student_count: Optional[int] = None
    instructor: Optional[str] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("")
def list_all_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str = "",
    keyword: str = "",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理列表（全部课程）"""
    query = db.query(Course)

    if category:
        query = query.filter(Course.category == category)
    if keyword:
        query = query.filter(Course.title.ilike(f"%{keyword}%"))

    total = query.count()
    courses = query.order_by(Course.sort_order.asc(), Course.id.desc()) \
                   .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for c in courses:
        items.append({
            "id": c.id,
            "title": c.title,
            "subtitle": c.subtitle,
            "description": c.description,
            "cover_url": c.cover_url,
            "category": c.category,
            "price": c.price,
            "duration": c.duration,
            "lesson_count": c.lesson_count,
            "student_count": c.student_count,
            "instructor": c.instructor,
            "is_published": c.is_published,
            "sort_order": c.sort_order,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
def create_course(
    req: CourseCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建课程"""
    course = Course(**req.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return {
        "id": course.id,
        "message": "创建成功",
    }


@router.put("/{course_id}")
def update_course(
    course_id: int,
    req: CourseUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新课程"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "课程不存在")

    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(course, key, value)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除课程"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "课程不存在")
    db.delete(course)
    db.commit()
    return {"message": "删除成功"}
