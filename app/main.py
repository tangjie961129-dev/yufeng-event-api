"""
屿风活动报名小程序 - FastAPI 入口
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.routers import auth, events, registration, admin_auth, admin_dashboard, admin_users, admin_business, admin_ui_config, admin_permission_distribution, public_ui_config, love, wx_kf, wecom_oauth, admin_cms, admin_member_tags, admin_ops, love_courses, admin_courses, quiz, admin_quiz, admin_rules, invite_router, admin_invite, partner_router, admin_partners_standalone, register_form, admin_stats
from app.routers.cooperation import user_router as cooperation_user_router, admin_router as admin_cooperation_router
from app.routers.admin_auth import ensure_default_admin
from app.routers.admin_permission_distribution import ensure_default_role_permissions

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")

# 注册路由
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(registration.router)
app.include_router(admin_auth.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_users.router)
app.include_router(admin_business.router)
app.include_router(admin_ui_config.router)
app.include_router(admin_permission_distribution.router)
app.include_router(admin_permission_distribution.user_router)
app.include_router(public_ui_config.router)
app.include_router(love.router)
app.include_router(love_courses.router)
app.include_router(quiz.router)
app.include_router(wx_kf.router)
app.include_router(wecom_oauth.router)
app.include_router(admin_courses.router)
app.include_router(admin_quiz.router)
app.include_router(admin_cms.router)
app.include_router(admin_member_tags.router)
app.include_router(admin_ops.router)
app.include_router(cooperation_user_router)
app.include_router(admin_cooperation_router)
app.include_router(admin_rules.router)
app.include_router(invite_router.router)
app.include_router(admin_invite.router)
app.include_router(admin_stats.router)
app.include_router(register_form.router)
app.include_router(partner_router.router)
app.include_router(admin_partners_standalone.router)

# 渠道主管理后台独立入口（不用 Nginx 额外配置）
from app.routers.partner_router import admin_dashboard_page as _partner_admin_page
from fastapi import APIRouter as _APIRouter
_partner_admin_router = _APIRouter()
_partner_admin_router.get("/api/yf-partner-admin")(_partner_admin_page)
app.include_router(_partner_admin_router)


@app.on_event("startup")
def startup():
    """启动时自动创建数据库表"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        ensure_default_role_permissions(db)
    finally:
        db.close()


@app.get("/admin/quiz")
def admin_quiz_page():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "admin-quiz.html"))


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
