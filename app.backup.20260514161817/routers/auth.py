"""
微信登录 & 用户认证 API
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.models.event import OrganizerCertification
from app.models.user import User
from app.schemas import (
    CertApplyRequest,
    CertInfo,
    MatchGroupConfig,
    MatchRecordInfo,
    UserInfo,
    WxLoginRequest,
    WxLoginResponse,
)

router = APIRouter(prefix="/api", tags=["用户认证"])


def _safe_json_load(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _safe_json_dump(value):
    return json.dumps(value, ensure_ascii=False)


def _status_key(status_text: str) -> str:
    if status_text == "成功":
        return "success"
    if status_text == "已结束":
        return "ended"
    return "ongoing"


def _build_invite_code(record: dict) -> str:
    record_id = str(record.get("id") or "YF-MATCH").upper().replace("_", "-")
    return record_id[:20]


def _build_share_message(user: User, record: dict) -> str:
    partner = record.get("nickname") or "匹配对象"
    nickname = user.nickname or "屿风用户"
    return f"{nickname}，你和 {partner} 的匹配沟通群已准备好。扫码进群后先看欢迎语，再完成第一句自我介绍。"


def _build_invite_tips() -> list[str]:
    return [
        "扫码后优先阅读欢迎消息，先完成一句真实自我介绍。",
        "若二维码失效，可点击刷新二维码获取最新进群码。",
        "建议 24 小时内完成第一次有效互动，避免关系冷启动失败。",
    ]


def _has_real_wecom_group_config() -> bool:
    return bool(
        settings.WECOM_REAL_GROUP_ENTRY_URL
        or settings.WECOM_REAL_GROUP_QR_URL
        or settings.WECOM_GROUP_JOIN_WAY_ID
    )


def _get_wecom_access_token() -> str:
    if not settings.WECOM_CORP_ID or not settings.WECOM_SECRET:
        return ""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{settings.WECOM_API_BASE}/cgi-bin/gettoken",
                params={
                    "corpid": settings.WECOM_CORP_ID,
                    "corpsecret": settings.WECOM_SECRET,
                },
            )
            data = resp.json()
    except Exception:
        return ""
    if data.get("errcode") != 0:
        return ""
    return data.get("access_token", "")


def _fetch_wecom_join_way_url() -> str:
    if settings.WECOM_REAL_GROUP_ENTRY_URL:
        return settings.WECOM_REAL_GROUP_ENTRY_URL
    if settings.WECOM_REAL_GROUP_QR_URL:
        return settings.WECOM_REAL_GROUP_QR_URL
    if not settings.WECOM_GROUP_JOIN_WAY_ID:
        return ""

    token = _get_wecom_access_token()
    if not token:
        return ""

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{settings.WECOM_API_BASE}/cgi-bin/externalcontact/groupchat/get_join_way",
                params={"access_token": token},
                json={"config_id": settings.WECOM_GROUP_JOIN_WAY_ID},
            )
            data = resp.json()
    except Exception:
        return ""

    if data.get("errcode") != 0:
        return ""

    join_way = data.get("join_way", {}) or {}
    for key in ("qr_code", "qr_code_url"):
        value = join_way.get(key)
        if value:
            return value
    return ""


def _get_real_group_entry_url() -> str:
    if not _has_real_wecom_group_config():
        return ""
    return _fetch_wecom_join_way_url()


def _build_qr_payload(user: User, record: dict) -> str:
    invite_code = _build_invite_code(record)
    partner = record.get("nickname") or "匹配对象"
    return "\n".join([
        settings.WECOM_GROUP_INVITE_LINK or "https://yufeng.team/invite/match",
        f"invite_code={invite_code}",
        f"match_id={record.get('id') or ''}",
        f"user_id={user.id}",
        f"nickname={user.nickname or '屿风用户'}",
        f"partner={partner}",
    ])


def _match_qr_relpath(user: User, record: dict, version_seed: str = "") -> str:
    raw = f"{user.id}:{record.get('id') or 'match'}:{version_seed}"
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"match-qrcodes/user-{user.id}-{record.get('id') or 'match'}-{suffix}.png"


def _ensure_qr_image(user: User, record: dict, force: bool = False) -> str:
    version_seed = datetime.now(timezone.utc).isoformat() if force else "stable"
    relpath = _match_qr_relpath(user, record, version_seed=version_seed)
    preferred_root = settings.UPLOAD_DIR
    candidate_roots = [preferred_root, os.path.join(os.getcwd(), ".runtime-uploads")]

    last_error = None
    for root in candidate_roots:
        try:
            abs_path = os.path.join(root, relpath)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            if force or not os.path.exists(abs_path):
                payload = _build_qr_payload(user, record)
                image = qrcode.make(payload)
                image.save(abs_path)
            return relpath
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"二维码生成失败: {last_error}")


def _public_static_url(relpath: str) -> str:
    encoded = "/".join(quote(part) for part in relpath.split("/"))
    return f"https://yufeng.team/static/{encoded}"


def _default_group_config(user: User, record: dict) -> dict:
    real_entry_url = _get_real_group_entry_url()
    relpath = _ensure_qr_image(user, record, force=False)
    local_qr_url = _public_static_url(relpath)
    qr_url = real_entry_url or local_qr_url
    share_link = real_entry_url or settings.WECOM_GROUP_INVITE_LINK or qr_url
    using_real_wecom = bool(real_entry_url)
    return {
        "status": "qr_ready" if qr_url else "pending",
        "chatid": "",
        "open_chat_supported": False,
        "open_chat_method": "wecom-group-join-way" if using_real_wecom else "qr-card",
        "open_chat_payload": qr_url,
        "fallback_qr_url": qr_url,
        "fallback_reason": "已切换为真实企微群入口，请直接扫码进群。" if using_real_wecom else ("已生成专属二维码，请扫码进群。" if qr_url else "群二维码待生成"),
        "invite_title": settings.WECOM_GROUP_INVITE_TITLE or "屿风匹配沟通群",
        "invite_subtitle": settings.WECOM_GROUP_INVITE_SUBTITLE or "扫码入群后先看欢迎消息，再完成第一句破冰",
        "invite_code": _build_invite_code(record),
        "invite_tips": _build_invite_tips(),
        "share_message": _build_share_message(user, record),
        "share_link": share_link,
        "qr_expires_at": "企微真实群码优先；若环境缺失则自动回退本地码",
        "welcome_message": {
            "title": "欢迎加入匹配沟通群",
            "content": f"Hi {user.nickname or '屿风用户'}，已为你和 {record.get('nickname', '匹配对象')} 准备好专属沟通群。进群后建议先用一句真实、轻松的话完成破冰。",
        },
        "qr_image_path": relpath,
        "group_source": "wecom-real" if using_real_wecom else "local-fallback",
        "join_way_id": settings.WECOM_GROUP_JOIN_WAY_ID or "",
    }


def _default_match_records(user: User):
    first_record = {
        "id": "match-demo-1",
        "nickname": "林川",
        "age": 29,
        "city": "广州",
        "match_type": "AI红娘",
        "match_type_key": "ai",
        "match_time": "2026-05-09 20:30",
        "status": "成功",
        "status_key": "success",
        "summary": "共同偏好安静社交、周末短途出行与长期稳定关系。",
        "score": 92,
    }
    first_record["group_config"] = _default_group_config(user, first_record)
    return [
        first_record,
        {
            "id": "match-demo-2",
            "nickname": "周屿",
            "age": 31,
            "city": "深圳",
            "match_type": "形婚搭子",
            "match_type_key": "marriage",
            "match_time": "2026-05-03 14:10",
            "status": "已结束",
            "status_key": "ended",
            "summary": "双方目标明确，已完成初步沟通与线下见面。",
            "score": 84,
            "group_config": None,
        },
    ]


def _get_match_records(user: User):
    records = _safe_json_load(user.match_records_json, [])
    if isinstance(records, list) and records:
        return records
    records = _default_match_records(user)
    user.match_records_json = _safe_json_dump(records)
    return records


def _build_user_info(user: User) -> UserInfo:
    records = _get_match_records(user)
    items = []
    for item in records:
        group_config = item.get("group_config")
        group_model = MatchGroupConfig(**group_config) if isinstance(group_config, dict) else None
        items.append(MatchRecordInfo(
            id=item.get("id", ""),
            nickname=item.get("nickname", ""),
            age=item.get("age") or 0,
            city=item.get("city", ""),
            match_type=item.get("match_type", "AI红娘"),
            match_type_key=item.get("match_type_key", "ai"),
            match_time=item.get("match_time", ""),
            status=item.get("status", "进行中"),
            status_key=item.get("status_key", _status_key(item.get("status", "进行中"))),
            summary=item.get("summary", ""),
            score=item.get("score") or 0,
            group_config=group_model,
        ))
    return UserInfo(
        id=user.id,
        nickname=user.nickname or "",
        avatar_url=user.avatar_url or "",
        avatar=user.avatar_url or "",
        phone=user.phone or "",
        age=user.age or 0,
        city=user.city or "",
        points=user.points or 0,
        member_level=user.member_level or 0,
        is_organizer=user.is_organizer if user.is_organizer else False,
        organizer_verified=user.organizer_verified if user.organizer_verified else False,
        role_tag="认真社交",
        personality_tag="长期关系向",
        subtitle="把订单、权益、匹配、收藏和反馈都收进一个更清晰的个人中心。",
        points_history=_safe_json_load(user.points_history_json, []),
        match_records=items,
    )


def _build_group_config(record: dict, current_user: User, force_refresh: bool = False) -> dict:
    existing = record.get("group_config") or {}
    base = _default_group_config(current_user, record)
    if force_refresh:
        real_entry_url = _get_real_group_entry_url()
        relpath = _ensure_qr_image(current_user, record, force=not bool(real_entry_url))
        qr_url = real_entry_url or _public_static_url(relpath)
        using_real_wecom = bool(real_entry_url)
        base["open_chat_payload"] = qr_url
        base["fallback_qr_url"] = qr_url
        base["share_link"] = real_entry_url or settings.WECOM_GROUP_INVITE_LINK or qr_url
        base["fallback_reason"] = "已刷新为最新企微群入口，请扫码进群。" if using_real_wecom else "已刷新为最新二维码，请扫码进群。"
        base["qr_image_path"] = relpath
        base["open_chat_method"] = "wecom-group-join-way" if using_real_wecom else "qr-card"
        base["group_source"] = "wecom-real" if using_real_wecom else "local-fallback"

    merged = dict(base)
    merged.update({
        "status": existing.get("status") or base["status"],
        "chatid": existing.get("chatid", ""),
        "open_chat_supported": False,
        "open_chat_method": base.get("open_chat_method") if force_refresh else (existing.get("open_chat_method") or base["open_chat_method"]),
        "open_chat_payload": base["open_chat_payload"] if force_refresh else (existing.get("open_chat_payload") or base["open_chat_payload"]),
        "fallback_qr_url": base["fallback_qr_url"] if force_refresh else (existing.get("fallback_qr_url") or base["fallback_qr_url"]),
        "fallback_reason": base["fallback_reason"] if force_refresh else (existing.get("fallback_reason") or base["fallback_reason"]),
        "invite_title": existing.get("invite_title") or base["invite_title"],
        "invite_subtitle": existing.get("invite_subtitle") or base["invite_subtitle"],
        "invite_code": existing.get("invite_code") or base["invite_code"],
        "invite_tips": existing.get("invite_tips") or base["invite_tips"],
        "share_message": existing.get("share_message") or base["share_message"],
        "share_link": base["share_link"] if force_refresh else (existing.get("share_link") or base["share_link"]),
        "qr_expires_at": base["qr_expires_at"] if force_refresh else (existing.get("qr_expires_at") or base["qr_expires_at"]),
        "welcome_message": existing.get("welcome_message") or base["welcome_message"],
        "group_source": base.get("group_source") if force_refresh else (existing.get("group_source") or base.get("group_source", "local-fallback")),
        "join_way_id": existing.get("join_way_id") or base.get("join_way_id", ""),
    })
    if not merged["fallback_qr_url"]:
        merged["status"] = "pending"
        merged["fallback_reason"] = "群二维码待生成"
    else:
        merged["status"] = "qr_ready"
    return merged


@router.post("/wx-login", response_model=WxLoginResponse)
async def wx_login(req: WxLoginRequest, db: Session = Depends(get_db)):
    """微信小程序登录"""
    if not settings.WX_SECRET:
        raise HTTPException(400, "请先在 .env 中配置 WX_SECRET")

    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.WX_LOGIN_URL, params={
            "appid": settings.WX_APPID,
            "secret": settings.WX_SECRET,
            "js_code": req.code,
            "grant_type": "authorization_code",
        })
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        raise HTTPException(400, f"微信登录失败: {data.get('errmsg', 'unknown')}")

    openid = data["openid"]

    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        user = User(openid=openid, nickname=req.nickname or "", avatar_url=req.avatar_url or "")
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if req.nickname and not user.nickname:
            user.nickname = req.nickname
        if req.avatar_url and not user.avatar_url:
            user.avatar_url = req.avatar_url
        if req.nickname or req.avatar_url:
            db.commit()
            db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return WxLoginResponse(token=token, user=_build_user_info(user))


@router.get("/user/profile", response_model=UserInfo)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户信息"""
    records = _get_match_records(user)
    for item in records:
        if item.get("status") == "成功":
            item["group_config"] = _build_group_config(item, user)
    user.match_records_json = _safe_json_dump(records)
    db.commit()
    db.refresh(user)
    return _build_user_info(user)


@router.get("/match/{match_id}/group-config", response_model=MatchGroupConfig)
def get_match_group_config(match_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = _get_match_records(user)
    target = None
    for item in records:
        if item.get("id") == match_id:
            target = item
            break
    if not target:
        raise HTTPException(404, "匹配记录不存在")
    if target.get("status") != "成功":
        raise HTTPException(400, "当前匹配状态未到成功，暂不可进入群聊")

    target["group_config"] = _build_group_config(target, user)
    user.match_records_json = _safe_json_dump(records)
    db.commit()
    db.refresh(user)
    return MatchGroupConfig(**target["group_config"])


@router.post("/match/{match_id}/refresh-group-qr", response_model=MatchGroupConfig)
def refresh_match_group_qr(match_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = _get_match_records(user)
    target = None
    for item in records:
        if item.get("id") == match_id:
            target = item
            break
    if not target:
        raise HTTPException(404, "匹配记录不存在")
    if target.get("status") != "成功":
        raise HTTPException(400, "当前匹配状态未到成功，暂不可刷新二维码")

    target["group_config"] = _build_group_config(target, user, force_refresh=True)
    user.match_records_json = _safe_json_dump(records)
    db.commit()
    db.refresh(user)
    return MatchGroupConfig(**target["group_config"])


@router.post("/match/{match_id}/mark-group-created", response_model=MatchGroupConfig)
def mark_match_group_created(
    match_id: str,
    chatid: str = Query("", min_length=0),
    qr_url: str = Query("", min_length=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = _get_match_records(user)
    target = None
    for item in records:
        if item.get("id") == match_id:
            target = item
            break
    if not target:
        raise HTTPException(404, "匹配记录不存在")

    group_config = _build_group_config(target, user)
    if qr_url:
        group_config["fallback_qr_url"] = qr_url
        group_config["open_chat_payload"] = qr_url
        group_config["share_link"] = qr_url
        group_config["group_source"] = "manual-override"
    if chatid:
        group_config["chatid"] = chatid
    group_config["status"] = "qr_ready" if group_config.get("fallback_qr_url") else "pending"
    group_config["open_chat_supported"] = False
    if not group_config.get("open_chat_method"):
        group_config["open_chat_method"] = "qr-card"
    group_config["fallback_reason"] = "已生成最新二维码，请扫码进群。" if group_config.get("fallback_qr_url") else "群二维码待生成"
    target["group_config"] = group_config

    user.match_records_json = _safe_json_dump(records)
    db.commit()
    db.refresh(user)
    return MatchGroupConfig(**group_config)


@router.post("/user/update-profile", response_model=UserInfo)
def update_profile(
    nickname: str = "",
    avatar_url: str = "",
    phone: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户信息"""
    if nickname:
        user.nickname = nickname
    if avatar_url:
        user.avatar_url = avatar_url
    if phone:
        user.phone = phone
    db.commit()
    db.refresh(user)
    return _build_user_info(user)


# ====== 主办方认证 ======

@router.post("/cert/apply", response_model=CertInfo)
def apply_certification(
    req: CertApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交主办方资质认证申请"""
    existing = db.query(OrganizerCertification).filter(
        OrganizerCertification.user_id == user.id
    ).first()
    if existing:
        if existing.status == "pending":
            raise HTTPException(400, "认证申请已在审核中，请耐心等待")
        if existing.status == "approved":
            raise HTTPException(400, "您已经是认证主办方")
        existing.real_name = req.real_name
        existing.phone = req.phone
        existing.id_card = req.id_card
        existing.qualification = json.dumps(req.qualification, ensure_ascii=False)
        existing.intro = req.intro
        existing.status = "pending"
        existing.reject_reason = ""
        existing.reviewed_by = None
        existing.reviewed_at = None
    else:
        cert = OrganizerCertification(
            user_id=user.id,
            real_name=req.real_name,
            phone=req.phone,
            id_card=req.id_card,
            qualification=json.dumps(req.qualification, ensure_ascii=False),
            intro=req.intro,
        )
        db.add(cert)

    db.commit()
    cert = db.query(OrganizerCertification).filter(
        OrganizerCertification.user_id == user.id
    ).first()
    return _cert_to_info(cert)


@router.get("/cert/status", response_model=CertInfo)
def get_cert_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查看认证状态"""
    cert = db.query(OrganizerCertification).filter(
        OrganizerCertification.user_id == user.id
    ).first()
    if not cert:
        return CertInfo(
            id=0, user_id=user.id, real_name="", phone="",
            id_card="", qualification=[], intro="",
            status="none", reject_reason="",
            created_at=datetime.now(timezone.utc),
        )
    return _cert_to_info(cert)


def _cert_to_info(cert):
    quals = []
    try:
        quals = json.loads(cert.qualification) if isinstance(cert.qualification, str) else (cert.qualification or [])
    except (json.JSONDecodeError, TypeError):
        quals = []

    return CertInfo(
        id=cert.id,
        user_id=cert.user_id,
        real_name=cert.real_name or "",
        phone=cert.phone or "",
        id_card=cert.id_card or "",
        qualification=quals,
        intro=cert.intro or "",
        status=cert.status or "pending",
        reject_reason=cert.reject_reason or "",
        created_at=cert.created_at or datetime.now(timezone.utc),
    )
