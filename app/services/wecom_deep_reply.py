"""企微客服异步深度回复服务 — 仅处理AI创作类需求。

只在员工需要「怎么写回复」「帮我想个话术」这类场景才走异步 DeepSeek。
查询/匹配类已经由 wx_kf.py 同步处理，不走这里。
"""
from __future__ import annotations

import time

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.member_profile import MemberProfile
from app.services.wecom import send_text_to_employee


def _compact(text: str, limit: int = 700) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _extract_customer_name(text: str) -> str | None:
    """从「怎么回小明」「帮小王写个话术」中提取客户名"""
    text = str(text or "").strip()
    for marker in ["客户", "会员", "给", "帮"]:
        if marker in text:
            tail = text.split(marker, 1)[1].strip("：: ，,。\n\t")
            if tail:
                return tail[:24]
    return None


def _find_context_profiles(db, content: str, limit: int = 3) -> list[MemberProfile]:
    """查找相关会员档案作为DeepSeek的上下文"""
    hint = _extract_customer_name(content)
    if not hint:
        return []
    from sqlalchemy import or_
    like = f"%{hint}%"
    return (
        db.query(MemberProfile)
        .filter(or_(MemberProfile.nickname.ilike(like), MemberProfile.city.ilike(like)))
        .order_by(MemberProfile.updated_at.desc())
        .limit(limit)
        .all()
    )


def _profile_line(profile: MemberProfile) -> str:
    parts = [
        profile.nickname or "未命名会员",
        profile.city or "城市未知",
        f"{profile.age}岁" if profile.age else "",
    ]
    detail = " / ".join(p for p in parts if p)
    more = "；".join([x for x in [profile.hobbies, profile.current_situation, profile.expectation] if x])
    return _compact(f"{detail}。补充：{more}", 240)


async def _call_deepseek(content: str, full_context: str) -> str:
    """调用 DeepSeek 生成回复草稿"""
    api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
    if not api_key:
        return (
            "━━━ ✍️ 回复草稿 ━━━\n\n"
            f"员工原话：{_compact(content, 180)}\n\n"
            f"{full_context}\n\n"
            "你可以这样回复客户：\n"
            "你好，我这边先根据你的资料和择偶期待做一轮初筛。"
            "屿风会更看重真实资料、城市距离、关系目标和沟通意愿。\n\n"
            "(AI不可用，以上为系统备选)"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "你是屿风男同性恋交友平台的 AI 助理「屿风小助理」，"
                "帮助员工为客户写回复和话术。\n\n"
                "【核心职责】\n"
                "当员工问「怎么回」「帮我想个回复」「写个话术」等时，"
                "给出可直接复制给客户的自然回复草稿。\n\n"
                "【回答规则】\n"
                "· 输出格式：「客户可见回复」+「员工备注」\n"
                "· 中文、自然、专业、温暖但不油腻\n"
                "· 隐藏性角色（不对外展示0/1标签）\n"
                "· 敏感信息：手机号只露尾号4位，微信号只露前4位\n"
                "· 不承诺包成功\n"
                "· 总字数控制在500字内"
            ),
        },
        {
            "role": "user",
            "content": (
                f"员工原话：{content}\n\n"
                f"相关会员档案参考：\n{full_context}"
            ),
        },
    ]
    started_at = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": messages, "max_tokens": 700, "temperature": 0.4},
            )
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            elapsed = int((time.perf_counter() - started_at) * 1000)
            print(f"[wx_kf] DeepSeek 深度回复成功, len={len(result)}, cost={elapsed}ms")
            return result
    except Exception as e:
        print(f"[wx_kf] DeepSeek 深度回复失败: {e}")
        return (
            "━━━ ✍️ 回复草稿 ━━━\n\n"
            "你可以这样回复客户：\n"
            "你好，感谢你的信任。屿风始终重视真实资料的匹配，"
            "我们这边会先根据你的信息和期待筛选合适的对象，"
            "有结果会第一时间推送给你。\n\n"
            "(AI生成失败，以上为系统备选)"
        )


async def generate_and_send_deep_reply(employee_userid: str, content: str) -> None:
    """后台生成深度回复，并主动推送给员工。异常吞掉，避免影响企微回调。"""
    if not employee_userid or not content:
        return
    db = SessionLocal()
    try:
        profiles = _find_context_profiles(db, content)
        context_parts = []
        if profiles:
            context_parts.append("【相关会员档案】")
            context_parts.append("\n".join(f"{idx}. {_profile_line(p)}" for idx, p in enumerate(profiles, 1)))
        else:
            context_parts.append("暂未在会员档案中命中明确对象。")

        full_context = "\n".join(context_parts)
        reply = await _call_deepseek(content, full_context)
        text = "━━━ ✍️ 回复草稿已生成 ━━━\n\n" + _compact(reply, 2000)
        await send_text_to_employee(employee_userid, text)
    except Exception:
        return
    finally:
        db.close()
