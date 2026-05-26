"""
企微 API 服务：客户联系 + 企业标签管理（个人微信客户适用）

不再依赖 OAuth（个人微信用户不支持），改用员工指定客户名查询 external_userid 后打标签。
"""
import json
import time
import uuid
from pathlib import Path

import httpx
from app.core.config import settings

WECOM_API_BASE = settings.WECOM_API_BASE or "https://qyapi.weixin.qq.com"


def _mask_secret(value: str, keep: int = 4) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= keep * 2:
        return value[:1] + "***"
    return value[:keep] + "..." + value[-keep:]


def _log_wecom_event(stage: str, **kwargs) -> None:
    """Single-line JSON log for WeCom diagnostics; never print access_token/secret."""
    safe = {k: v for k, v in kwargs.items() if v is not None}
    safe.setdefault("stage", stage)
    print("[wecom] " + json.dumps(safe, ensure_ascii=False, default=str), flush=True)


def _explain_wecom_errcode(errcode: int | None, errmsg: str = "") -> str:
    """Convert common WeCom errcodes into a short human-readable diagnosis."""
    mapping = {
        81013: "收件人无效：通常是 touser 不是企微 userid，或应用可见范围不足。",
        40001: "鉴权失败：access_token 无效或已过期。",
        40014: "参数错误：通常是 appid/secret/token 配置或请求参数不合法。",
        40013: "CorpID 或应用配置不正确。",
        60111: "无权限或应用未启用客户/消息能力。",
        60102: "无效的部门/成员范围。",
    }
    if errcode in mapping:
        return mapping[errcode]
    if errmsg:
        return errmsg
    return "未知企微错误。"


# ─── Access Token ────────────────────────────────────────────────

_access_token_cache: str | None = None
_access_token_expires_at: float = 0


async def _get_access_token() -> str:
    """获取企微自建应用的 access_token（需开通客户联系权限）"""
    global _access_token_cache, _access_token_expires_at
    now = time.time()
    if _access_token_cache and now < _access_token_expires_at:
        return _access_token_cache

    request_id = uuid.uuid4().hex[:8]
    _log_wecom_event(
        "token_request",
        request_id=request_id,
        corpid=_mask_secret(settings.WECOM_CORP_ID),
        agentid=settings.WECOM_AGENT_ID,
        has_secret=bool(settings.WECOM_APP_SECRET),
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/cgi-bin/gettoken",
            params={"corpid": settings.WECOM_CORP_ID, "corpsecret": settings.WECOM_APP_SECRET},
            timeout=10,
        )
        data = resp.json()
        errcode = data.get("errcode")
        _log_wecom_event(
            "token_response",
            request_id=request_id,
            http_status=resp.status_code,
            errcode=errcode,
            errmsg=data.get("errmsg"),
            expires_in=data.get("expires_in"),
        )
        if errcode != 0:
            raise RuntimeError(f"获取 access_token 失败: {data}")
        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)

    _access_token_cache = token
    _access_token_expires_at = now + expires_in - 30
    return token


async def create_contact_way_for_channel(
    employee_userid: str,
    state: str,
    remark: str = "",
    skip_verify: bool = True,
) -> dict:
    employee_userid = (employee_userid or "").strip()
    if not employee_userid:
        raise ValueError("创建企微联系我二维码需要填写企微员工ID")
    token = await _get_access_token()
    payload = {
        "type": 1,
        "scene": 2,
        "style": 1,
        "remark": (remark or "屿风引流渠道")[:30],
        "skip_verify": bool(skip_verify),
        "state": (state or "")[:100],
        "user": [employee_userid],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/add_contact_way",
            params={"access_token": token},
            json=payload,
        )
    data = resp.json()
    _log_wecom_event(
        "contact_way_create",
        http_status=resp.status_code,
        errcode=data.get("errcode"),
        errmsg=data.get("errmsg"),
        state=payload.get("state"),
        employee_userid=employee_userid,
        has_qr=bool(data.get("qr_code")),
        config_id=data.get("config_id"),
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"创建企微联系我二维码失败: {data}")
    data["request_payload"] = payload
    return data


def get_contact_way_by_welcome_code_sync(welcome_code: str) -> dict:
    """Resolve a customer-contact callback WelcomeCode into contact-way metadata.

    WeCom add_external_contact/change_external_contact callbacks for contact-way QR
    codes may omit State, but include WelcomeCode. The get_contact_way API returns
    the original state/config_id so attribution can be recovered synchronously in
    the callback path.
    """
    import asyncio
    import httpx

    welcome_code = (welcome_code or "").strip()
    if not welcome_code:
        return {}

    async def _run() -> dict:
        token = await _get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{WECOM_API_BASE}/cgi-bin/externalcontact/get_contact_way",
                params={"access_token": token},
                json={"welcome_code": welcome_code},
            )
        data = resp.json()
        _log_wecom_event(
            "contact_way_get_by_welcome_code",
            http_status=resp.status_code,
            errcode=data.get("errcode"),
            errmsg=data.get("errmsg"),
            has_contact_way=bool(data.get("contact_way")),
        )
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取企微联系我方式失败: {data}")
        return data.get("contact_way") or {}

    return asyncio.run(_run())


# ─── 查找客户 external_userid ──────────────────────────────────


async def find_external_userid(
    employee_userid: str,
    customer_name: str,
) -> str | None:
    """在员工的外部联系人列表中，按名字查找客户的 external_userid"""
    token = await _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/batch/get_by_user",
            params={"access_token": token},
            json={
                "userid_list": [employee_userid],
                "limit": 100,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取客户列表失败: {data}")

    customer_list = data.get("external_contact_list", [])
    for item in customer_list:
        contact = item.get("external_contact") or {}
        name = (contact.get("name") or "").strip()
        ext_id = contact.get("external_userid")
        if ext_id and customer_name in name:
            return ext_id

    return None


# ─── 企业标签管理 ──────────────────────────────────────────────

TAG_GROUP_NAME = "屿风会员画像"
# 注意：group_id 由企微自动生成，不要写死；通过 ensure_tag_group() 获取实际值


async def ensure_tag_group() -> str:
    """确保「屿风会员画像」标签组存在，返回其 group_id"""
    token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/get_corp_tag_list",
            params={"access_token": token},
            json={},
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"查询标签失败: {data}")

        for group in data.get("tag_group", []):
            if group.get("group_name") == TAG_GROUP_NAME:
                return group["group_id"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/add_corp_tag",
            params={"access_token": token},
            json={
                "group_name": TAG_GROUP_NAME,
                "tag": [{"name": "层级·C"}],
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"创建标签组失败: {data}")
        return data["tag_group"]["group_id"]


async def ensure_tag(tag_name: str) -> str:
    """确保标签存在，返回 tag_id"""
    token = await _get_access_token()
    # 先拿到真实 group_id
    group_id = await ensure_tag_group()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/get_corp_tag_list",
            params={"access_token": token},
            json={},
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"查询标签失败: {data}")

        for group in data.get("tag_group", []):
            if group.get("group_id") == group_id:
                for tag in group.get("tag", []):
                    if tag["name"] == tag_name:
                        return tag["id"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/add_corp_tag",
            params={"access_token": token},
            json={
                "group_id": group_id,
                "tag": [{"name": tag_name}],
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"创建标签失败: {data}")
        # 响应结构：{errcode:0, tag_group: {group_id, group_name, tag: [{id, name}]}}
        tag_group = data.get("tag_group") or {}
        tags = tag_group.get("tag", [])
        if not tags:
            raise RuntimeError(f"创建标签后未返回 tag 信息: {data}")
        return tags[-1]["id"]


# ─── 打标签 ─────────────────────────────────────────────────────


async def mark_tag(external_userid: str, tag_ids: list[str], employee_userid: str = "") -> None:
    """给客户打标签。employee_userid 标记是哪位员工的外部联系人"""
    token = await _get_access_token()
    payload = {
        "external_userid": external_userid,
        "add_tag": tag_ids,
    }
    if employee_userid:
        payload["userid"] = employee_userid
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/mark_tag",
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"打标签失败: {data}")


# ─── 修改客户备注 ─────────────────────────────────────────────


async def remark_external_contact(
    employee_userid: str,
    external_userid: str,
    remark: str,
    description: str = "",
    remark_pic_mediaid: str = "",
) -> bool:
    """修改员工名下外部联系人的备注/描述。"""
    token = await _get_access_token()
    payload = {
        "userid": employee_userid,
        "external_userid": external_userid,
        "remark": (remark or "")[:20],
    }
    if description:
        payload["description"] = description[:150]
    if remark_pic_mediaid:
        payload["remark_pic_mediaid"] = remark_pic_mediaid
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/remark",
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"修改客户备注失败: {data}")
        return True


async def upload_wecom_image_media(image_path: str) -> str:
    """上传图片到企微临时素材，返回 media_id。用于 remark_pic_mediaid。"""
    token = await _get_access_token()
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError(f"图片文件不存在: {image_path}")
    mime = "image/jpeg"
    if path.suffix.lower() == ".png":
        mime = "image/png"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"
    elif path.suffix.lower() == ".gif":
        mime = "image/gif"
    async with httpx.AsyncClient() as client:
        with path.open("rb") as f:
            resp = await client.post(
                f"{WECOM_API_BASE}/cgi-bin/media/upload",
                params={"access_token": token, "type": "image"},
                files={"media": (path.name, f, mime)},
                timeout=20,
            )
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"上传企微图片素材失败: {data}")
    media_id = data.get("media_id")
    if not media_id:
        raise RuntimeError(f"上传企微图片素材未返回 media_id: {data}")
    return media_id


# ─── 给员工发企微消息 ─────────────────────────────────────────


async def send_text_to_employee(
    employee_userid: str,
    content: str,
) -> bool:
    """通过企微自建应用给员工发送文本消息"""
    request_id = uuid.uuid4().hex[:8]
    token = await _get_access_token()
    payload = {
        "touser": employee_userid,
        "msgtype": "text",
        "agentid": settings.WECOM_AGENT_ID,
        "text": {"content": content},
        "safe": 0,
    }
    _log_wecom_event(
        "message_send_request",
        request_id=request_id,
        touser=employee_userid,
        agentid=settings.WECOM_AGENT_ID,
        content_len=len(content or ""),
        content_preview=(content or "")[:120],
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/message/send",
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
        data = resp.json()
        _log_wecom_event(
            "message_send_response",
            request_id=request_id,
            http_status=resp.status_code,
            errcode=data.get("errcode"),
            errmsg=data.get("errmsg"),
            invaliduser=data.get("invaliduser"),
            invalidparty=data.get("invalidparty"),
            invalidtag=data.get("invalidtag"),
            touser=employee_userid,
            agentid=settings.WECOM_AGENT_ID,
            diagnosis=_explain_wecom_errcode(data.get("errcode"), data.get("errmsg", "")),
        )
        if data.get("errcode") != 0:
            raise RuntimeError(f"发送消息失败: {data}")
        return True


# ─── 根据表单数据自动生成标签列表 ─────────────────────────────


def _age_to_group(age_str: str) -> str | None:
    """把年龄（数字或文本）转为标签用的年龄段"""
    age_str = age_str.strip()
    if not age_str:
        return None
    try:
        age = int(age_str)
    except ValueError:
        return None
    if age <= 17:
        return None
    elif age <= 22:
        return "18-22"
    elif age <= 27:
        return "23-27"
    elif age <= 32:
        return "28-32"
    elif age <= 38:
        return "33-38"
    else:
        return "39+"


def _income_score(income: str) -> int:
    text = (income or "").lower().replace(" ", "")
    if not text:
        return 0
    import re
    nums = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)(w|万)?", text):
        n = float(m.group(1))
        if m.group(2) in ("w", "万"):
            n *= 10000
        nums.append(n)
    high = max(nums) if nums else 0
    if high >= 30000 or "高" in text:
        return 30
    if high >= 20000:
        return 24
    if high >= 10000:
        return 14
    if high > 0:
        return 8
    return 0


def evaluate_member_level(form_data: dict) -> str:
    """运营层级 S/A/B/C：5 维评分模型。"""
    from app.services.member_scorer import score_member
    # member_scorer 期望 profile 具有完整字段
    # form_data 来自登记表，缺省字段补空字符串
    profile = {
        "income": form_data.get("income", ""),
        "city": form_data.get("city", ""),
        "role_self": form_data.get("role_self", ""),
        "ideal_role": form_data.get("ideal_role", ""),
        "birth_info": str(form_data.get("age", "") or ""),
        "nickname": form_data.get("nickname", ""),
        "height": form_data.get("height", ""),
        "weight": form_data.get("weight", ""),
        "body_type": form_data.get("body_type", ""),
        "job": form_data.get("job", ""),
        "education": form_data.get("education", ""),
        "hobbies": form_data.get("hobbies", ""),
        "current_situation": form_data.get("current_situation", ""),
        "expectation": form_data.get("expectation", ""),
        "ideal_desc": form_data.get("ideal_desc", form_data.get("expectation", "")),
        "dealbreaker": form_data.get("dealbreaker", ""),
        "marriage": form_data.get("marriage", ""),
        "photos": form_data.get("photos", ""),
        "lifestyle_status": form_data.get("lifestyle_status", ""),
        "long_distance": form_data.get("long_distance", ""),
    }
    level, _, _ = score_member(profile)
    return level


def suggest_tags_from_form(form_data: dict) -> list[str]:
    """根据表单数据生成标签：层级 + 城市"""
    tags = [f"层级·{evaluate_member_level(form_data)}"]
    city = (form_data.get("city") or "").strip()
    if city:
        tags.append(f"城市·{city}")
    return tags



async def upload_media_image(image_path: str) -> dict:
    """Upload a local image to WeCom temporary media and return raw response with media_id."""
    import mimetypes
    image_path = str(image_path or "").strip()
    if not image_path:
        raise ValueError("image_path is required")
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    token = await _get_access_token()
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    async with httpx.AsyncClient(timeout=60) as client:
        with path.open("rb") as f:
            resp = await client.post(
                f"{WECOM_API_BASE}/cgi-bin/media/upload",
                params={"access_token": token, "type": "image"},
                files={"media": (path.name, f, content_type)},
            )
    data = resp.json()
    _log_wecom_event(
        "media_upload_image",
        http_status=resp.status_code,
        errcode=data.get("errcode"),
        errmsg=data.get("errmsg"),
        file=str(path),
        size=path.stat().st_size,
        has_media_id=bool(data.get("media_id")),
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"上传企微图片失败: {data}")
    return data


async def upload_attachment_resource(image_path: str) -> dict:
    """通过「上传附件资源」接口上传图片，返回media_id用于朋友圈/群发等。
    和 media/upload（普通消息素材）不同，attachment_type='moments'。
    """
    import mimetypes
    image_path = str(image_path or "").strip()
    if not image_path:
        raise ValueError("image_path is required")
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    token = await _get_access_token()
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    async with httpx.AsyncClient(timeout=60) as client:
        with path.open("rb") as f:
            resp = await client.post(
                f"{WECOM_API_BASE}/cgi-bin/media/upload_attachment",
                params={"access_token": token, "media_type": "image", "attachment_type": "1"},
                files={"media": (path.name, f, content_type)},
            )
    data = resp.json()
    _log_wecom_event(
        "upload_attachment_resource",
        http_status=resp.status_code,
        errcode=data.get("errcode"),
        errmsg=data.get("errmsg"),
        file=str(path),
        size=path.stat().st_size,
        has_media_id=bool(data.get("media_id")),
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"上传企微附件资源失败: {data}")
    return data


async def add_moment_task(
    content: str,
    image_media_ids: list[str] | None = None,
    sender_users: list[str] | None = None,
    # sender_tags was here - use external_tags instead for tag targeting
    external_tags: list[str] | None = None,
    exclude_external_tags: list[str] | None = None,
) -> dict:
    """Create a WeCom Customer Moments task (待发表任务) via externalcontact/add_moment_task."""
    content = (content or "").strip()
    if not content:
        raise ValueError("朋友圈文案不能为空")
    token = await _get_access_token()
    payload: dict = {"text": {"content": content}}
    attachments = []
    for media_id in image_media_ids or []:
        media_id = (media_id or "").strip()
        if media_id:
            attachments.append({"msgtype": "image", "image": {"media_id": media_id}})
    if attachments:
        payload["attachments"] = attachments
    visible_range: dict = {}
    sender_list: dict = {}
    if sender_users:
        sender_list["user_list"] = [x for x in sender_users if x]
    # sender_tags not supported in moments sender_list
    if sender_list:
        visible_range["sender_list"] = sender_list
    external_list: dict = {}
    if external_tags:
        external_list["tags"] = [x for x in external_tags if x]
    if exclude_external_tags:
        external_list["exclude_external_tags"] = [x for x in exclude_external_tags if x]
    if external_list:
        visible_range["external_list"] = external_list
    if visible_range:
        payload["visible_range"] = visible_range

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/externalcontact/add_moment_task",
            params={"access_token": token},
            json=payload,
        )
    data = resp.json()
    _log_wecom_event(
        "add_moment_task",
        http_status=resp.status_code,
        errcode=data.get("errcode"),
        errmsg=data.get("errmsg"),
        content_len=len(content),
        image_count=len(attachments),
        sender_users=sender_users,
        has_jobid=bool(data.get("jobid") or data.get("moment_id")),
    )
    if data.get("errcode") != 0:
        raise RuntimeError(f"创建企微客户朋友圈任务失败: {data}")
    data["request_payload"] = payload
    return data
