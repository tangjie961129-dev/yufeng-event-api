"""
企微 API 服务：客户联系 + 企业标签管理（个人微信客户适用）

不再依赖 OAuth（个人微信用户不支持），改用员工指定客户名查询 external_userid 后打标签。
"""
import httpx
from app.core.config import settings

WECOM_API_BASE = settings.WECOM_API_BASE or "https://qyapi.weixin.qq.com"

# ─── Access Token ────────────────────────────────────────────────

_access_token_cache: str | None = None
_access_token_expires_at: float = 0


async def _get_access_token() -> str:
    """获取企微自建应用的 access_token（需开通客户联系权限）"""
    import time
    global _access_token_cache, _access_token_expires_at
    now = time.time()
    if _access_token_cache and now < _access_token_expires_at:
        return _access_token_cache

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{WECOM_API_BASE}/cgi-bin/gettoken",
            params={"corpid": settings.WECOM_CORP_ID, "corpsecret": settings.WECOM_APP_SECRET},
            timeout=10,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取 access_token 失败: {data}")
        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)

    _access_token_cache = token
    _access_token_expires_at = now + expires_in - 30
    return token


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
                "tag": [{"name": "已填表"}],
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


# ─── 给员工发企微消息 ─────────────────────────────────────────


async def send_text_to_employee(
    employee_userid: str,
    content: str,
) -> bool:
    """通过企微自建应用给员工发送文本消息"""
    token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{WECOM_API_BASE}/cgi-bin/message/send",
            params={"access_token": token},
            json={
                "touser": employee_userid,
                "msgtype": "text",
                "agentid": settings.WECOM_AGENT_ID,
                "text": {"content": content},
                "safe": 0,
            },
            timeout=10,
        )
        data = resp.json()
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


def suggest_tags_from_form(form_data: dict) -> list[str]:
    """根据表单数据推荐标签（新版表单）"""
    tags = ["已填表"]

    city = (form_data.get("city") or "").strip()
    if city:
        tags.append(f"城市·{city}")

    # 年龄：可能是数字"30"→转为年龄组标签
    age = (form_data.get("age") or "").strip()
    if age:
        group = _age_to_group(age)
        if group:
            tags.append(f"年龄·{group}")

    role = (form_data.get("role_self") or "").strip()
    if role and role not in ("", "不限", "都可以", "无所谓"):
        tags.append(f"角色·{role}")

    # 收入标签
    income = (form_data.get("income") or "").strip()
    if income:
        tags.append(f"收入·{income}")

    # 体型标签
    body_type = (form_data.get("body_type") or "").strip()
    if body_type:
        tags.append(f"体型·{body_type}")

    # 从多个长文字段判断态度
    text_fields = [
        form_data.get("lifestyle_status", ""),
        form_data.get("hobbies", ""),
        form_data.get("current_situation", ""),
        form_data.get("expectation", ""),
    ]
    total_text_len = sum(len((t or "").strip()) for t in text_fields)
    if total_text_len > 150:
        tags.append("态度·认真型")
    elif total_text_len > 0:
        tags.append("态度·已填写")

    # 如果期待你的文字里提到"接受异地"→打接受异地标签
    expectation = (form_data.get("expectation") or "").strip()
    if "异地" in expectation and "接受" in expectation:
        tags.append("接受异地")
    elif "异地" in expectation and "不" in expectation:
        tags.append("仅同城")

    # 独立的"是否接受短暂异地"字段
    long_distance = (form_data.get("long_distance") or "").strip()
    if long_distance == "接受":
        tags.append("接受异地")
    elif long_distance == "不接受":
        tags.append("仅同城")

    return tags
