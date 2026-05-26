"""内容中心(CMS) 与 会员标签 数据库模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON

from app.core.database import Base


class CmsCategory(Base):
    """内容分类"""
    __tablename__ = "cms_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    key = Column(String(100), unique=True, nullable=False)
    icon = Column(String(200), default="")
    color = Column(String(20), default="#7c3aed")
    description = Column(String(500), default="")
    sort_order = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CmsBanner(Base):
    """内容 Banner"""
    __tablename__ = "cms_banners"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="")
    subtitle = Column(String(500), default="")
    image_url = Column(String(500), default="")
    target_url = Column(String(500), default="")
    page = Column(String(50), default="home")  # home/love
    sort_order = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CmsPageWidget(Base):
    """页面组件"""
    __tablename__ = "cms_page_widgets"

    id = Column(Integer, primary_key=True)
    page = Column(String(50), nullable=False)  # home/love/test
    widget_type = Column(String(50), nullable=False)  # hero_banner/features_grid/course_list/activity_list/quiz_entry
    config = Column(JSON, default=dict)
    sort_order = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CmsAnnouncement(Base):
    """系统公告"""
    __tablename__ = "cms_announcements"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="")
    content = Column(Text, default="")
    link_url = Column(String(500), default="")
    is_published = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MemberTag(Base):
    """会员标签"""
    __tablename__ = "member_tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), default="general")
    color = Column(String(20), default="#409EFF")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemberProfileTag(Base):
    """会员-标签关联"""
    __tablename__ = "member_profile_tags"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("member_profiles.id"))
    tag_id = Column(Integer, ForeignKey("member_tags.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
