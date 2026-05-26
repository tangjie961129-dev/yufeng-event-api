"""
屿风恋爱课程公开 API
"""
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.course import Course

router = APIRouter(prefix="/api/love/courses", tags=["恋爱课程"])


@router.get("")
def list_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str = "",
    keyword: str = "",
    db: Session = Depends(get_db),
):
    """公开课程列表（只返回已发布）"""
    query = db.query(Course).filter(Course.is_published == True)

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
            "sort_order": c.sort_order,
            "created_at": c.created_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{course_id}")
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
):
    """公开课程详情"""
    course = db.query(Course).filter(Course.id == course_id, Course.is_published == True).first()
    if not course:
        raise HTTPException(404, "课程不存在")
    return {
        "id": course.id,
        "title": course.title,
        "subtitle": course.subtitle,
        "description": course.description,
        "cover_url": course.cover_url,
        "category": course.category,
        "price": course.price,
        "duration": course.duration,
        "lesson_count": course.lesson_count,
        "student_count": course.student_count,
        "instructor": course.instructor,
        "sort_order": course.sort_order,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }
