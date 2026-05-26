"""
课程系统模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(500), default="")
    description = Column(Text, default="")
    cover_url = Column(String(500), default="")
    category = Column(String(100), default="")
    price = Column(Float, default=0.0)
    duration = Column(String(50), default="")
    lesson_count = Column(Integer, default=0)
    student_count = Column(Integer, default=0)
    instructor = Column(String(100), default="")
    is_published = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    course_id = Column(Integer, nullable=False, index=True)
    progress = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
