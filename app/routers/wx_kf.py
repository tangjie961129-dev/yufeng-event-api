"""微信客服 / 企业微信回调 — 集成专属填表链接生成 + 同步查询/匹配

员工在自建应用中说「给清风徐来发链接」或「查XX档案」或「推荐匹配」
→ 同步返回结果（不走异步），只有AI创作类才走异步深度回复。

回复格式统一：
━━━ 功能名 ━━━

[内容]

💡 下一步：[可操作的建议]
"""
import base64
import hashlib
import re
import struct
import time
import xml.etree.ElementTree as ET
from urllib.parse import unquote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.registration_link import RegistrationLink
from app.models.member_profile import MemberProfile
from app.models.huxuan_profile import HuxuanProfile
from app.services.wecom_deep_reply import generate_and_send_deep_reply
from app.services.wecom_reply import (
    _build_daily_preview_reply,
    _build_member_info_reply,
    _build_menu_reply,
    _build_rules_reply,
    _build_text_reply_xml,
    _update_rule,
)
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s|%(name)s|%(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wecom", tags=["企微自建应用回调"])


class WecomCallbackError(RuntimeError):
    pass


# ─── 加解密工具 ───────────────────────────────────────────────


def _get_token_and_aes_key() -> tuple[str, str]:
    token = getattr(settings, "WECOM_TOKEN", "") or getattr(settings, "WX_KF_TOKEN", "")
    aes_key = getattr(settings, "WECOM_ENCODING_AES_KEY", "") or getattr(settings, "WX_KF_ENCODING_AES_KEY", "")
    if not token or not aes_key:
        raise WecomCallbackError("missing WECOM_TOKEN or WECOM_ENCODING_AES_KEY")
    if len(aes_key) != 43:
        raise WecomCallbackError("WECOM_ENCODING_AES_KEY must be 43 chars")
    return token, aes_key


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise WecomCallbackError("empty plaintext")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 32:
        raise WecomCallbackError("invalid pkcs7 padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise WecomCallbackError("bad pkcs7 padding bytes")
    return data[:-pad_len]


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len


def _verify_signature(token: str, timestamp: str, nonce: str, encrypted: str, msg_signature: str) -> None:
    parts = sorted([token, timestamp, nonce, encrypted])
    digest = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    if digest != msg_signature:
        raise WecomCallbackError("invalid msg_signature")


def _decrypt_message(encrypted: str, aes_key: str) -> str:
    """解密企微回调消息体"""
    key = base64.b64decode(aes_key + "=")
    if len(key) != 32:
        raise WecomCallbackError("decoded aes key must be 32 bytes")
    iv = key[:16]
    ciphertext = base64.b64decode(encrypted)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    plaintext = _pkcs7_unpad(plaintext)
    if len(plaintext) < 20:
        raise WecomCallbackError("plaintext too short")
    msg_len = struct.unpack(">I", plaintext[16:20])[0]
    msg_start = 20
    msg_end = msg_start + msg_len
    if msg_end > len(plaintext):
        raise WecomCallbackError("invalid message length")
    return plaintext[msg_start:msg_end].decode("utf-8")


def _encrypt_message(plain_xml: str, aes_key: str, corpid: str) -> str:
    """加密回复消息体"""
    key = base64.b64decode(aes_key + "=")
    if len(key) != 32:
        raise WecomCallbackError("decoded aes key must be 32 bytes")
    iv = key[:16]

    raw = plain_xml.encode("utf-8")
    msg_len = struct.pack(">I", len(raw))
    rand_bytes = b"\x00" * 16  # 16 字节随机串（简化处理）
    corpid_bytes = corpid.encode("utf-8")

    to_encrypt = rand_bytes + msg_len + raw + corpid_bytes
    padded = _pkcs7_pad(to_encrypt)

    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("utf-8")


def _encrypt_reply(plain_xml: str, token: str, aes_key: str, corpid: str) -> str:
    """将回复 XML 加密并组装签名，返回最终的响应体"""
    encrypted = _encrypt_message(plain_xml, aes_key, corpid)
    timestamp = str(int(time.time()))
    nonce = str(int(time.time() * 1000) % 1000000)

    parts = sorted([token, timestamp, nonce, encrypted])
    signature = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()

    return f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""


# ─── URL 验证（GET） ─────────────────────────────────────────


def verify_url(msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
    token, aes_key = _get_token_and_aes_key()
    encrypted = unquote(echostr)
    _verify_signature(token, timestamp, nonce, encrypted, msg_signature)
    return _decrypt_message(encrypted, aes_key)


@router.get("/callback")
def wecom_callback_verify(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企业微信自建应用 URL 验证"""
    try:
        plain = verify_url(msg_signature, timestamp, nonce, echostr)
    except WecomCallbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=plain, media_type="text/plain; charset=utf-8")


# ─── 消息解析 ───────────────────────────────────────────────


def _parse_message_xml(xml_text: str) -> dict:
    """解析企微回调的 XML 消息"""
    root = ET.fromstring(xml_text)
    result = {}
    for child in root:
        result[child.tag] = child.text or ""
    return result


def _strip_remark_suffix(name: str) -> str:
    """去除备注后缀｜城市｜属性｜年龄｜等级，只保留昵称"""
    idx = name.find("｜")
    if idx > 0:
        return name[:idx].strip()
    return name.strip()


def _extract_customer_name(text: str) -> str | None:
    """从「给清风徐来发链接」中提取客户名（自动去除备注后缀）"""
    m = re.search(r"给(.+?)发(?:个|个的|)?(?:填表)?链接", text)
    if m:
        return _strip_remark_suffix(m.group(1))
    return None


def _extract_query_name(text: str) -> str | None:
    """从「查XX的档案/打听XX」中提取客户名"""
    # 查XX的档案
    m = re.search(r"查(.+?)(?:的档案|的情况|的资料|的)?$", text)
    if m:
        return m.group(1).strip()
    # 打听XX
    m = re.search(r"打听(.+?)(?:的|$)", text)
    if m:
        return m.group(1).strip()
    return None


# ─── 同步查询/匹配（在回调内直接完成，不靠异步 DeepSeek） ────



def _query_by_city_role(db, content):
    """粗查询：按城市+属性筛选会员
    说「查西安的1」「查广州的0」「深圳0.5」「北京的side」
    同时查 users、member_profiles、huxuan_profiles
    """
    import re
    m = re.search(r"(?:查|找)?\s*(.+?)\s*的\s*(0|1|0\.5|side|双|其他)\s*$", content)
    if not m:
        m = re.search(r"(?:查|找)?\s*(.+?)\s*([0-9.]+|side|双)\s*$", content)
    if not m:
        return None
    city_search = m.group(1).strip()
    role_search = m.group(2).strip()
    if not city_search or not role_search:
        return None
    from app.models.member_profile import MemberProfile
    from app.models.huxuan_profile import HuxuanProfile
    seen = set()
    combined = []
    for mp in db.query(MemberProfile).filter(
        MemberProfile.nickname.isnot(None), MemberProfile.nickname != "",
        MemberProfile.city.ilike(f"%{city_search}%"),
        MemberProfile.role_self == role_search,
    ).order_by(MemberProfile.age.asc().nullslast()).limit(20).all():
        k = (mp.nickname or "").strip()
        if k and k not in seen:
            seen.add(k); combined.append(("mp", mp))
    # 暂不包含 users（模型缺 role_self 字段）
    for h in db.query(HuxuanProfile).filter(
        HuxuanProfile.昵称.isnot(None), HuxuanProfile.昵称 != "",
        HuxuanProfile.城市.ilike(f"%{city_search}%"),
        HuxuanProfile.属性 == role_search,
    ).limit(20).all():
        k = (h.昵称 or "").strip()
        if k and k not in seen:
            seen.add(k); combined.append(("hx", h))
    if not combined:
        return (
            "\u2501\u2501\u2501 \U0001f50d \u7c97\u67e5\u8be2 \u2501\u2501\u2501\n\n"
            f"\u672a\u627e\u5230\u300c{city_search}\u300d\u7684{role_search}\n\n"
            "\U0001f4a1 \u53ef\u8bf4\u300c\u67e5XX\u7684\u6863\u6848\u300d\u5355\u4e2a\u67e5\u8be2"
        )
    combined = combined[:20]
    out = [f"\u2501\u2501\u2501 \U0001f50d {city_search}\u7684{role_search} \u2501\u2501\u2501", ""]
    out.append(f"\u5171\u67e5\u5230 {len(combined)} \u4f4d\u4f1a\u5458\uff1a\n")
    for i, (src, e) in enumerate(combined, 1):
        if src == "hx":
            nm = e.昵称 or "?"; ct = e.城市 or "?"
            ag = f"{e.年龄}\u5c81" if e.年龄 else "?"
            bd = e.体型 or "?"; jb = e.职业 or "?"
        else:
            nm = e.nickname or "?"; ct = e.city or "?"
            ag = f"{e.age}\u5c81" if e.age else "?"
            bd = e.body_type or "?"; jb = e.job or "?"
        out.append(f"{i}. {nm} | {ct} | {ag} | {bd} | {jb}")
        out.append(f"   \U0001f4a1 \u8bf4\u300c\u67e5{nm}\u7684\u6863\u6848\u300d\u67e5\u770b\u8be6\u7ec6")
    out.append("")
    out.append("\U0001f4a1 \u53ef\u8bf4\u300c\u67e5\u5176\u4ed6\u57ce\u5e02\u7684X\u300d\u7ee7\u7eed\u7b5b\u9009")
    return "\n".join(out)
def _query_member_sync(db: Session, content: str) -> str | None:
    """同步查会员档案，直接返回格式化结果"""
    query_name = _extract_query_name(content)

    # 如果是推荐匹配类，走匹配逻辑
    if any(kw in content for kw in ["推荐", "匹配", "介绍", "推荐匹配"]):
        return None  # 留给 _recommend_match_sync

    if not query_name:
        return None

    like = f"%{query_name}%"

    # 先查 users 总表（用户说要从总表查，人更多）
    from app.models.user import User
    from sqlalchemy import or_
    user = db.query(User).filter(or_(
        User.nickname.ilike(like),
        User.city.ilike(like),
    )).order_by(User.updated_at.desc()).first()

    if user:
        return _build_member_info_reply(user)

    # 再查 member_profiles（登记档案，数据更全）
    profile = db.query(MemberProfile).filter(
        MemberProfile.nickname.ilike(like)
    ).order_by(MemberProfile.updated_at.desc()).first()

    if profile:
        try:
            from datetime import datetime, timezone
            profile.last_contact_at = datetime.now(timezone.utc)
            db.flush()
        except:
            pass
        return _build_member_info_reply(profile)

    return None


def _recommend_match_sync(db: Session, content: str, employee_userid: str) -> str:
    """同步推荐匹配 — 使用 matching_service 的6维度评分引擎
    - 说「推荐匹配 王五」→ 以王五为基准匹配
    - 说「推荐匹配」→ 显示提示
    """
    from app.services.matching_service import find_matches
    import re

    # 1. 尝试从内容中提取人名
    # 去掉触发关键词，剩下的部分作为人名
    cleaned = content.strip()
    for kw in ["推荐匹配", "给", "推荐", "匹配", "介绍", " "]:
        cleaned = cleaned.replace(kw, " ")
    cleaned = cleaned.strip()

    ref_profile = None
    if cleaned:
        ref_profile = db.query(MemberProfile).filter(
            MemberProfile.nickname.ilike(f"%{cleaned}%"),
        ).first()

    if ref_profile:
        matches = find_matches(db, ref_profile, limit=5)
        if not matches:
            return (
                "━━━ 💞 推荐匹配 ━━━\n\n"
                f"以「{ref_profile.nickname}」为基准，暂无匹配候选人。\n\n"
                "💡 下一步：换个会员试试"
            )

        lines = [
            f"━━━ 💞 以{ref_profile.nickname}为基准匹配 ━━━",
            f"📋 {ref_profile.city or '?'} · {ref_profile.age or '?'}岁 · {ref_profile.role_self or '?'}",
            "",
        ]
        for i, m in enumerate(matches, 1):
            p = m["profile"]
            s = m["scores"]
            name = getattr(p, "nickname", getattr(p, "昵称", "?"))
            city = getattr(p, "city", getattr(p, "城市", ""))
            lines.append(f"{i}. {name} | 💯 {s['total']}%")
            lines.append(f"   {city} · 角色{s['role']} · 年龄{s['age']} · 体型{s['body']}")
            bonus = s.get("city_bonus", 0)
            if bonus:
                lines.append(f"   {'📍 同城 ✓' if bonus >= 20 else '📍 同省'}")
            lines.append("")
        lines.append("💡 说「查XX的档案」查看详细信息")
        return "\n".join(lines)

    # 2. 没有指定人名 → 引导
    return (
        "━━━ 💞 推荐匹配 ━━━\n\n"
        "请指定要匹配的基准会员，例如：\n"
        "· 说「推荐匹配 张三」\n"
        "· 或先给客户发填表链接，填表后系统自动推送匹配\n\n"
        "💡 说「给XX发填表链接」让客户先登记资料"
    )


# ─── 回复格式统一 ────────────────────────────────────────────


def _build_greeting_reply() -> str:
    return (
        "━━━ 🤖 屿风小助理 ━━━\n\n"
        "你可以直接输入指令：\n"
        "· 说「给XX发填表链接」→ 生成客户专属登记链接\n"
        "· 说「查XX的档案」→ 查询会员完整信息\n"
        "· 说「推荐匹配」→ 获取匹配建议\n"
        "· 说「打听XX」→ 了解某个会员的情况\n\n"
        "💡 需要什么帮助尽管说~"
    )


def _build_unknown_reply() -> str:
    return (
        "━━━ 🤖 屿风小助理 ━━━\n\n"
        "没理解你的意思，你可以试试：\n"
        "·「给XX发填表链接」→ 生成客户专属登记链接\n"
        "·「查XX的档案」→ 查询会员信息\n"
        "·「推荐匹配」→ 获取匹配建议\n"
        "·「打听XX」→ 了解某个会员的情况"
    )


# ─── 深度回复触发判断 ────────────────────────────────────────


def _should_trigger_deep_reply(content: str) -> bool:
    """判断是否该走异步AI创作类深度回复

    只有以下场景走异步：
    - 员工问「怎么回」「帮我想」「给个...」
    - 请求话术、回复建议
    """
    text = content.strip().lower()
    trigger_keywords = [
        "怎么回", "怎么回复", "帮我想", "给个", "话术",
        "帮写", "写个", "给个回复", "想个",
    ]
    return any(kw in text for kw in trigger_keywords)


# ─── 主动推送回复（超出企微回调长度限制时的备选方案） ───────


async def _push_long_reply(employee_userid: str, content: str) -> None:
    """通过企微主动推送长消息（回调回复有长度限制时备用）"""
    try:
        from app.services.wecom import send_text_to_employee
        await send_text_to_employee(employee_userid, content)
    except Exception:
        logger.exception("wx_kf: push_long_reply failed")


# ─── 主回调 ──────────────────────────────────────────────────


@router.post("/callback")
async def wecom_callback_event(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """处理企微自建应用的消息回调

    消息处理层级（状态机）：
    1. 菜单事件 → 菜单回复文本（统一格式）
    2. 文本消息 →
       ├─ 「给XX发链接」→ 生成链接 + 简短确认
       ├─ 「查XX」「打听XX」→ 同步查询会员档案直接返回
       ├─ 「推荐/匹配」→ 同步匹配推荐直接返回
       ├─ 「怎么回」「帮我想」→ 简短确认 + 异步 DeepSeek 深度回复
       └─ 其他/问候 → 引导提示（不走异步）
    """
    body = await request.body()

    # ---------- 解密消息 ----------
    try:
        token, aes_key = _get_token_and_aes_key()
    except WecomCallbackError as e:
        logger.warning("wx_kf: missing token/AES key: %s", e)
        return Response(content="success", media_type="text/plain; charset=utf-8")

    try:
        raw_xml = body.decode("utf-8")
        enc_match = re.search(r"<Encrypt><!\[CDATA\[(.*?)\]\]></Encrypt>", raw_xml, re.DOTALL)
        if not enc_match:
            logger.warning("wx_kf: no <Encrypt> in incoming XML")
            return Response(content="success", media_type="text/plain; charset=utf-8")

        encrypted = enc_match.group(1)

        sig_match = re.search(r"<MsgSignature><!\[CDATA\[(.*?)\]\]></MsgSignature>", raw_xml)
        ts_match = re.search(r"<TimeStamp>(.*?)</TimeStamp>", raw_xml)
        nonce_match = re.search(r"<Nonce><!\[CDATA\[(.*?)\]\]></Nonce>", raw_xml)

        if sig_match and ts_match and nonce_match:
            _verify_signature(token, ts_match.group(1), nonce_match.group(1), encrypted, sig_match.group(1))

        decrypted = _decrypt_message(encrypted, aes_key)

    except Exception as e:
        logger.exception("wx_kf: decrypt/parse failed: %s", e)
        return Response(content="success", media_type="text/plain; charset=utf-8")

    # ---------- 解析消息 ----------
    try:
        msg = _parse_message_xml(decrypted)
        logger.warning("wx_kf callback: MsgType=%s EventKey=%s Content=%s",
                     msg.get("MsgType","?"), msg.get("EventKey",""), msg.get("Content","")[:80])
    except Exception:
        logger.exception("wx_kf: msg parse failed")
        return Response(content="success", media_type="text/plain; charset=utf-8")

    msg_type = msg.get("MsgType", "")
    content = msg.get("Content", "").strip()
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")

    # ---------- 处理事件消息 ----------
    if msg_type == "event":
        event = msg.get("Event", "")

        # 客户通过联系我二维码添加企微好友 → 自动确认佣金
        if event in ("add_external_contact", "change_external_contact"):
            try:
                decrypted_local = _decrypt_message(encrypted, aes_key)
                detail_root = ET.fromstring(decrypted_local)
                state = (detail_root.findtext("State") or "").strip()
                ext_userid = (detail_root.findtext("ExternalUserID") or "").strip()
                welcome_code = (detail_root.findtext("WelcomeCode") or "").strip()
                logger.warning("wx_kf: external_contact event=%s state=%s ext=%s", event, state, ext_userid)

                if state and state.startswith("partner_"):
                    partner_id = state.replace("partner_", "")
                    from app.core.database import SessionLocal
                    from app.routers.partner_router import (
                        ChannelPartner, PartnerRegister, Decimal as _D
                    )
                    sdb = SessionLocal()
                    try:
                        register = sdb.query(PartnerRegister).filter(
                            PartnerRegister.partner_id == partner_id,
                            PartnerRegister.status == "pending",
                        ).order_by(PartnerRegister.created_at.desc()).first()
                        if register:
                            register.status = "confirmed"
                            if ext_userid:
                                register.external_userid = ext_userid
                            pdb = sdb.query(ChannelPartner).filter(
                                ChannelPartner.partner_id == partner_id
                            ).first()
                            if pdb:
                                pdb.total_commission += _D("2.00")
                                pdb.total_deals = (pdb.total_deals or 0) + 1
                                pdb.withdrawable += _D("2.00")
                            sdb.commit()
                            logger.warning("wx_kf: 渠道主%s佣金自动确认-¥2.00", partner_id)

                            # ── 自动备注 ──
                            if pdb and ext_userid and pdb.employee_userid:
                                try:
                                    from app.services.wecom import remark_external_contact
                                    remark_text = f"渠道:{partner_id[:8]}"
                                    desc_text = f"渠道主:{pdb.name} 来源:微信 日期:{time.strftime('%Y-%m-%d')}"
                                    await remark_external_contact(
                                        employee_userid=pdb.employee_userid,
                                        external_userid=ext_userid,
                                        remark=remark_text,
                                        description=desc_text,
                                    )
                                    logger.warning("wx_kf: 渠道主%s客户备注已自动设置", partner_id)
                                except Exception:
                                    logger.exception("wx_kf: 自动备注失败")
                    except Exception:
                        logger.exception("wx_kf: 自动确认佣金失败")
                    finally:
                        sdb.close()
            except Exception as e:
                logger.warning("wx_kf: 解析外部联系人事件失败: %s", e)
            return Response(content="success", media_type="text/plain; charset=utf-8")

        # 对外收款回调 - 自动成交记录
        if event == "pay_for_external_user":
            try:
                detail_root = ET.fromstring(decrypted)
                ext_userid = (detail_root.findtext("ExternalUserID") or "").strip()
                pay_type = (detail_root.findtext("PayType") or "").strip()
                total_fee_str = (detail_root.findtext("TotalFee") or "0").strip()
                trade_state = (detail_root.findtext("TradeState") or "").strip()
                logger.warning("wx_kf: pay_callback ext=%s type=%s fee=%s state=%s",
                             ext_userid, pay_type, total_fee_str, trade_state)

                if trade_state != "success" or not ext_userid:
                    return Response(content="success", media_type="text/plain; charset=utf-8")

                total_fee_yuan = float(total_fee_str) / 100.0
                from app.core.database import SessionLocal
                from app.routers.partner_router import (
                    ChannelPartner, PartnerRegister, Decimal as _Dec
                )
                sdb = SessionLocal()
                try:
                    register = sdb.query(PartnerRegister).filter(
                        PartnerRegister.external_userid == ext_userid,
                        PartnerRegister.deal_amount == 0,
                    ).order_by(PartnerRegister.created_at.desc()).first()

                    if register:
                        old_status = register.status
                        register.deal_amount = _Dec(str(total_fee_yuan))
                        deal_fee = total_fee_yuan * 0.20
                        register.deal_fee = _Dec(str(deal_fee))
                        register.total_fee = _Dec(str(2.00 + deal_fee))
                        register.status = "dealt"

                        partner = sdb.query(ChannelPartner).filter(
                            ChannelPartner.partner_id == register.partner_id
                        ).first()
                        if partner:
                            partner.total_deals = (partner.total_deals or 0) + 1
                            partner.total_commission += _Dec(str(deal_fee))
                            partner.withdrawable += _Dec(str(deal_fee))

                        sdb.commit()
                        logger.warning(
                            "wx_kf: 自动成交记录成功 ext=%s 金额=¥%s 分佣=¥%s",
                            ext_userid, total_fee_yuan, deal_fee
                        )
                except Exception:
                    logger.exception("wx_kf: 自动成交记录失败")
                finally:
                    sdb.close()
            except Exception as e:
                logger.warning("wx_kf: 解析收款事件失败: %s", e)
            return Response(content="success", media_type="text/plain; charset=utf-8")

        if event == "click":
            event_key = msg.get("EventKey", "")
            # 朋友圈预览 → 动态查询
            ek_upper = event_key.upper().strip()
            is_preview = any(kw in ek_upper for kw in ["PREVIEW", "DAILY_PREVIEW", "朋友圈预览", "预览"])
            if is_preview:
                reply_text = _build_daily_preview_reply()
            else:
                reply_text = _build_menu_reply(event_key)
                if not reply_text:
                    reply_text = _build_greeting_reply()
            try:
                reply_xml = _build_text_reply_xml(from_user, to_user, reply_text)
                encrypted_reply = _encrypt_reply(reply_xml, token, aes_key, settings.WECOM_CORP_ID)
                return Response(content=encrypted_reply, media_type="application/xml; charset=utf-8")
            except Exception as e:
                logger.exception("wx_kf: menu click reply failed: %s", e)
                return Response(content="success", media_type="text/plain; charset=utf-8")
        return Response(content="success", media_type="text/plain; charset=utf-8")

    # ---------- 只处理文本消息 ----------
    if msg_type != "text" or not content:
        return Response(content="success", media_type="text/plain; charset=utf-8")

    # ========== 文本消息状态机 ==========

    # --- 层1：问候类 ---
    if any(kw in content for kw in ["你好", "在吗", "hi", "hello", "嗨", "在吗"]):
        reply_text = _build_greeting_reply()

    # --- 层2：修改规则 ---
    elif any(kw in content for kw in ["改成", "修改规则", "规则改成", "规则改为", "配图", "文案规则"]):
        # 检测 "把XX改成YYY" 模式 — 支持快速修改
        import re as _re
        m = _re.search(r"(?:把)?(.{1,8}?)(?:规则|文案|规则改成|改成|改为)[：:：]?(.{5,})", content)
        if m:
            rule_kw = m.group(1).strip()
            new_val = m.group(2).strip()
            success, msg = _update_rule(rule_kw, new_val)
            reply_text = msg if success else msg + "\n\n💡 也可以到网页修改：\nhttps://yufeng.team/api/admin/rules/"
        else:
            reply_text = (
                "━━━ ⚙️ 修改规则 ━━━\n\n"
                "请在网页端修改：\nhttps://yufeng.team/api/admin/rules/\n\n"
                "如需快速修改，说：\n"
                "「把配图规则改成……」"
            )

    # --- 层3：发链接指令（先核实客户存在） ---
    elif any(kw in content for kw in ["发链接", "发登记链接", "登记链接", "填表链接", "重新填表", "更新资料", "更新链接"]):
        customer_name = _extract_customer_name(content)

        if customer_name and from_user:
            # ── 先在企微中核实该客户是否存在 ──
            try:
                from app.services.wecom import find_external_userid
                found_id = await find_external_userid(from_user, customer_name)
            except Exception:
                found_id = None

            if not found_id:
                reply_text = (
                    "━━━ 🔗 发登记链接 ━━━\n\n"
                    f"⚠️ 在你的客户列表中未找到「{customer_name}」\n\n"
                    "可能原因：\n"
                    f"1. 客户「{customer_name}」尚未添加你的企业微信\n"
                    f"2. 客户名可能不一样，试试说「查XX的档案」先确认名字\n"
                    f"3. 如果确实是不同名，也可以直接手动发送登记链接\n\n"
                    f"💡 你也可以直接发这个通用登记链接给客户：\n"
                    f"https://yufeng.team/api/wecom/tag/register-form"
                )
            else:
                import uuid
                token_str = uuid.uuid4().hex
                link = RegistrationLink(
                    token=token_str,
                    employee_userid=from_user,
                    external_userid=found_id,
                    customer_name=customer_name,
                    status="pending",
                )
                db.add(link)
                db.commit()

                link_url = "https://yufeng.team/api/wecom/tag/register-form?" + "token=" + token_str

                is_update = any(kw in content for kw in ["重新填表", "更新资料", "更新链接"])
                _hint = "【更新资料】已有资料会被新填写的内容覆盖。请提醒客户认真填写。" if is_update else "他填表后会自动打标签。"
                reply_text = (
                    "━━━ 🔗 发登记链接 ━━━\n\n"
                    f"✅ 已为「{customer_name}」生成专属登记链接：\n"
                    f"{link_url}\n\n"
                    f"把链接发给 {customer_name}，{_hint}\n\n"
                    "💡 下一步：客户填表后说「查XX的档案」查看完整信息"
                )
        else:
            reply_text = (
                "━━━ 🔗 发登记链接 ━━━\n\n"
                "请说「给客户名字发填表链接」\n"
                "例如：给清风徐来发填表链接\n\n"
                "💡 系统将自动为该客户生成专属填表链接"
            )

    # --- 层3：查档案/打听 ---
    elif any(kw in content for kw in ["查", "打听", "档案"]):
        # 粗查询优先：按城市+属性筛选
        reply_text = _query_by_city_role(db, content)
        if not reply_text:
            reply_text = _query_member_sync(db, content)
            if not reply_text:
                query_name = _extract_query_name(content)
                if query_name:
                    reply_text = (
                        "\u2501\u2501\u2501 \U0001f4cb \u67e5\u4f1a\u5458\u6863\u6848 \u2501\u2501\u2501\n\n"
                        f"\u672a\u627e\u5230\u300c{query_name}\u300d\u7684\u6863\u6848\u4fe1\u606f\u3002\n\n"
                        f"\U0001f4a1 \u53ef\u80fd\u539f\u56e0\uff1a\u5ba2\u6237\u5c1a\u672a\u586b\u8868\u767b\u8bb0\uff0c\u8bf4\u300c\u7ed9{query_name}\u53d1\u586b\u8868\u94fe\u63a5\u300d\u8ba9\u4ed6\u5148\u586b\u8868"
                    )
                else:
                    reply_text = (
                        "\u2501\u2501\u2501 \U0001f4cb \u67e5\u4f1a\u5458\u6863\u6848 \u2501\u2501\u2501\n\n"
                        "\u8bf7\u8bf4\u300c\u67e5XX\u7684\u6863\u6848\u300d\u67e5\u770b\u4f1a\u5458\u4fe1\u606f\n"
                        "\u4f8b\u5982\uff1a\u67e5\u6e05\u98ce\u7684\u6863\u6848\n\n"
                        "\U0001f4a1 \u4e5f\u53ef\u8bf4\u300c\u6253\u542cXX\u300d\u4e86\u89e3\u57fa\u672c\u60c5\u51b5"
                    )
    # --- 层4：推荐匹配 ---
    elif any(kw in content for kw in ["推荐", "匹配", "推荐匹配", "介绍"]):
        reply_text = _recommend_match_sync(db, content, from_user)

    # --- 层5：AI创作类（怎么回、帮我想...）→ 异步深度回复 ---
    elif _should_trigger_deep_reply(content):
        reply_text = (
            "━━━ ✍️ 帮你写回复 ━━━\n\n"
            "收到，正在为你生成回复草稿，请稍候...\n\n"
            "💡 异步推送将在几秒后到达"
        )
        background_tasks.add_task(generate_and_send_deep_reply, from_user, content)

    # --- 层6：其他 ---
    else:
        reply_text = _build_unknown_reply()

    # ---------- 加密回复 ----------
    try:
        reply_xml = _build_text_reply_xml(from_user, to_user, reply_text)
        # 企微回调回复有长度限制（~2048字节明文），超长时用主动推送
        if len(reply_xml.encode("utf-8")) > 1800:
            logger.warning("wx_kf: reply too long (%d bytes), pushing async", len(reply_xml))
            background_tasks.add_task(_push_long_reply, from_user, reply_text)
            short_reply = (
                "━━━ 查询结果较长 ━━━\n\n"
                "结果较长，已通过消息推送到你的对话框，请查看。"
            )
            reply_xml = _build_text_reply_xml(from_user, to_user, short_reply)

        encrypted_reply = _encrypt_reply(reply_xml, token, aes_key, settings.WECOM_CORP_ID)
        logger.warning("wx_kf text reply: reply_xml_len=%d encrypted_len=%d", len(reply_xml), len(encrypted_reply))
        return Response(content=encrypted_reply, media_type="application/xml; charset=utf-8")
    except Exception:
        logger.exception("wx_kf: text reply encryption failed")
        return Response(content="success", media_type="text/plain; charset=utf-8")
