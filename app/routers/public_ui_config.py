"""公共 UI 配置 API（免登录）
供小程序首页读取 banner、分类、主题、联系信息等展示数据
"""
import json
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import CommissionSetting
from app.models.cms import CmsCategory, CmsBanner, CmsAnnouncement

router = APIRouter(prefix="/api/public", tags=["公共UI配置"])

DEFAULT_UI_CONFIG: dict[str, Any] = {
    "home": {
        "hero_title": "屿风",
        "hero_subtitle": "遇见有趣的人，发现精彩活动",
        "hero_image": "",
        "announcement": "本周精选活动已上新",
        "show_banner": True,
    },
    "theme": {
        "primary_color": "#3D3229",
        "accent_color": "#C9A962",
        "text_color": "#2C2420",
        "page_background": "#FAF8F5",
        "card_radius": 20,
    },
    "contact": {
        "service_wechat": "JLGHTJ",
        "service_phone": "13185500021",
        "service_email": "tangzengrong@yufengmedia.cn",
    },
    "banners": [
        {"id": "banner_1", "title": "精选活动", "subtitle": "官方推荐热门活动", "image_url": "", "enabled": True, "sort_order": 1},
        {"id": "banner_2", "title": "周末搭子", "subtitle": "适合周末快速组局", "image_url": "", "enabled": True, "sort_order": 2},
    ],
    "features": [
        {"key": "运动", "title": "运动", "icon": "medalfill", "enabled": True, "sort_order": 1},
        {"key": "旅行", "title": "旅行", "icon": "locationfill", "enabled": True, "sort_order": 2},
        {"key": "音乐", "title": "音乐", "icon": "musicfill", "enabled": True, "sort_order": 3},
        {"key": "户外", "title": "户外", "icon": "choicenessfill", "enabled": True, "sort_order": 4},
    ],
    "categories": [
        {"key": "微醺局", "color": "#C27B6B"},
        {"key": "徒步局", "color": "#7B9E6B"},
        {"key": "唱歌局", "color": "#7B8EA6"},
        {"key": "相亲局", "color": "#C9A962"},
        {"key": "沙龙局", "color": "#8C7E72"},
        {"key": "桌游局", "color": "#A88B4A"},
    ],
}


def _deep_clone_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_UI_CONFIG, ensure_ascii=False))


def _load_public_ui_config(setting: CommissionSetting | None) -> dict[str, Any]:
    merged = _deep_clone_default()
    if setting and getattr(setting, "ui_config_json", None):
        try:
            data = json.loads(setting.ui_config_json)
            if isinstance(data, dict):
                merged.update(data)
        except Exception:
            pass

    # 尝试从 CMS 表加载数据（无记录时回退到默认配置）
    return merged


@router.get("/ui-config")
def get_public_ui_config(
    db: Session = Depends(get_db),
):
    """小程序首页获取 UI 配置（banner、分类、主题色等），无需登录"""
    setting = db.query(CommissionSetting).first()
    result = _load_public_ui_config(setting)

    # ---- 从 CMS 表加载分类 ----
    cms_categories = (
        db.query(CmsCategory)
        .filter(CmsCategory.is_enabled == True)
        .order_by(CmsCategory.sort_order, CmsCategory.id)
        .all()
    )
    if cms_categories:
        result["categories"] = [
            {
                "key": c.key,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "description": c.description,
                "sort_order": c.sort_order,
            }
            for c in cms_categories
        ]

    # ---- 从 CMS 表加载首页 Banner ----
    cms_banners = (
        db.query(CmsBanner)
        .filter(CmsBanner.is_enabled == True, CmsBanner.page == "home")
        .order_by(CmsBanner.sort_order, CmsBanner.id)
        .all()
    )
    if cms_banners:
        result["banners"] = [
            {
                "id": f"banner_{b.id}",
                "title": b.title,
                "subtitle": b.subtitle,
                "image_url": b.image_url,
                "target_url": b.target_url,
                "enabled": b.is_enabled,
                "sort_order": b.sort_order,
            }
            for b in cms_banners
        ]

    # ---- 从 CMS 表加载公告 ----
    announcement = (
        db.query(CmsAnnouncement)
        .filter(CmsAnnouncement.is_published == True)
        .order_by(CmsAnnouncement.sort_order, CmsAnnouncement.id.desc())
        .first()
    )
    if announcement:
        result["announcement"] = {
            "id": announcement.id,
            "title": announcement.title,
            "content": announcement.content,
            "link_url": announcement.link_url,
        }
        # 同时更新 home.announcement 为标题
        result["home"]["announcement"] = announcement.title

    return result
