"""
管理员装修/UI 配置 API
"""
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.event import CommissionSetting
from app.schemas.admin import AdminUiConfigPayload, AdminUiConfigResponse

router = APIRouter(prefix="/api/admin/ui-config", tags=["后台UI配置"])

DEFAULT_UI_CONFIG: dict[str, Any] = {
    "home": {
        "hero_title": "屿风活动报名",
        "hero_subtitle": "发现真实、温暖、有质感的同城活动",
        "hero_image": "",
        "announcement": "欢迎来到屿风活动平台，报名后请留意审核与支付通知。",
        "show_banner": True,
    },
    "theme": {
        "primary_color": "#7c3aed",
        "accent_color": "#ec4899",
        "text_color": "#111827",
        "page_background": "#f8fafc",
        "card_radius": 20,
    },
    "contact": {
        "service_wechat": "JLGHTJ",
        "service_phone": "13185500021",
        "service_email": "tangzengrong@yufengmedia.cn",
    },
    "modules": {
        "show_notice": True,
        "show_banners": True,
        "show_categories": True,
        "show_contact": True,
        "show_feature_labels": True,
        "show_tabbar": True,
    },
    "banners": [
        {"id": "banner_1", "title": "推荐活动", "subtitle": "优先展示官方精选活动", "image_url": "", "target": "推荐活动", "enabled": True, "sort_order": 1},
        {"id": "banner_2", "title": "周末搭子", "subtitle": "适合周末快速组局", "image_url": "", "target": "周末搭子", "enabled": True, "sort_order": 2},
    ],
    "features": [
        {"key": "运动", "title": "运动", "description": "组织跑步、健身、球类等更有男人味的线下相聚。", "icon": "medalfill", "color": "red", "enabled": True, "sort_order": 1},
        {"key": "旅行", "title": "旅行", "description": "周边短途、城市探索、节假日搭子局。", "icon": "locationfill", "color": "cyan", "enabled": True, "sort_order": 2},
        {"key": "音乐", "title": "音乐", "description": "Livehouse、K歌、音乐节与共同聆听。", "icon": "musicfill", "color": "purple", "enabled": True, "sort_order": 3},
        {"key": "户外", "title": "户外", "description": "露营、徒步、飞盘和自然系社交。", "icon": "choicenessfill", "color": "green", "enabled": True, "sort_order": 4},
    ],
    "tabs": [
        {"key": "recommended", "label": "推荐活动", "icon": "fire-o", "page_path": "/pages/activities/activities", "enabled": True, "sort_order": 1},
        {"key": "weekend", "label": "周末搭子", "icon": "friends-o", "page_path": "/pages/activities/activities", "enabled": True, "sort_order": 2},
        {"key": "new", "label": "最新发布", "icon": "new-o", "page_path": "/pages/activities/activities", "enabled": True, "sort_order": 3},
    ],
    "tabbar": [
        {"key": "home", "label": "首页", "icon": "wap-home-o", "page_path": "/pages/index/index", "enabled": True, "sort_order": 1},
        {"key": "my", "label": "我的", "icon": "manager-o", "page_path": "/pages/myactivity/myactivity", "enabled": True, "sort_order": 2},
        {"key": "create", "label": "创建", "icon": "add-o", "page_path": "/pages/create_act/create_act", "enabled": True, "sort_order": 3},
        {"key": "moments", "label": "瞬间", "icon": "notes-o", "page_path": "/pages/moments/moments", "enabled": True, "sort_order": 4},
        {"key": "setting", "label": "设置", "icon": "setting-o", "page_path": "/pages/setting/setting", "enabled": True, "sort_order": 5},
    ],
}


def _deep_clone_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_UI_CONFIG, ensure_ascii=False))


def _sorted_enabled(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (item.get("sort_order", 0), item.get("title") or item.get("label") or item.get("key") or item.get("id") or ""))


def _normalize_ui_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    payload = AdminUiConfigPayload.model_validate(raw or {})
    data = payload.model_dump(mode="json")
    merged = _deep_clone_default()
    merged.update(data)
    merged["banners"] = _sorted_enabled(data.get("banners", []))
    merged["features"] = _sorted_enabled(data.get("features", []))
    merged["tabs"] = _sorted_enabled(data.get("tabs", []))
    merged["tabbar"] = _sorted_enabled(data.get("tabbar", []))
    return merged


def _load_ui_config(setting: CommissionSetting | None) -> dict[str, Any]:
    if not setting or not getattr(setting, "ui_config_json", None):
        return _deep_clone_default()
    try:
        data = json.loads(setting.ui_config_json)
        if isinstance(data, dict):
            return _normalize_ui_config(data)
    except Exception:
        pass
    return _deep_clone_default()


@router.get("", response_model=AdminUiConfigResponse)
def get_ui_config(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    setting = db.query(CommissionSetting).first()
    return _load_ui_config(setting)


@router.post("", response_model=AdminUiConfigResponse)
def update_ui_config(
    payload: AdminUiConfigPayload,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    setting = db.query(CommissionSetting).first()
    if not setting:
        setting = CommissionSetting(rate=10.0, min_fee=0, max_fee=None, updated_by=None)
        db.add(setting)
        db.flush()

    normalized = _normalize_ui_config(payload.model_dump(mode="json"))
    setting.ui_config_json = json.dumps(normalized, ensure_ascii=False)
    setting.updated_at = datetime.now(timezone.utc)
    db.commit()
    return normalized
