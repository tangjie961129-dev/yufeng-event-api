"""微信客服 / 企业微信回调 — 集成专属填表链接生成

员工在自建应用中说「给清风徐来发链接」或「给XXX发填表链接」
→ 自动生成专属链接 → 回复给员工
"""
import base64
import asyncio
import logging
import hashlib
import re
import struct
import time
import xml.etree.ElementTree as ET
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from httpx import AsyncClient
from app.models.registration_link import RegistrationLink
logger = logging.getLogger("yufeng.wx_kf")

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


# ─── Hermes AI 客服回复 ───────────────────────────────────────

HERMES_SYSTEM_PROMPT = (
    "你是屿风平台的客服回复助手，叫做\"屿风回复助手\"。\n"
    "你的定位：\n"
    "- 员工在企微自建应用里向你提问，可能是在问怎么回复客户的问题\n"
    "- 你需要给出专业、实用的回复建议\n"
    "- 屿风是一个男同性恋交友平台，会员体系为男同性恋群体\n"
    "- 语言风格温暖、专业、不油腻\n\n"
    "回复规则：\n"
    "- 如果是问怎么回复客户，直接给出可用的回复文本\n"
    "- 如果是日常问题（技术、流程等），正常回答\n"
    "- 回复简洁干脆，不要啰嗦开场白\n"
    "- 如果不知道，诚实说不知道"
)


async def _query_hermes_ai(user_message: str) -> str | None:
    """直连 DeepSeek API（绕过 Hermes 网关），企微要求 5s 内回复"""
    try:
        deepseek_key = settings.DEEPSEEK_API_KEY or ""
        if not deepseek_key:
            logger.error("DEEPSEEK_API_KEY not configured")
            return None

        async with AsyncClient(timeout=4.5) as http:
            resp = await http.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-v4-flash",
                    "messages": [
                        {"role": "system", "content": HERMES_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return text
            logger.warning("LLM API %%d: %%s", resp.status_code, resp.text[:200])
    except Exception:
        logger.error("AI call failed", exc_info=True)
    return None

async def _async_hermes_brain_push(user_message: str, from_user: str):
    """后台调 Hermes 网关（带 GBrain/工具），结果通过企微主动推送"""
    try:
        hermes_key = settings.HERMES_API_KEY or ""
        hermes_url = settings.HERMES_API_URL or "http://localhost:8642/v1/chat/completions"
        if not hermes_key:
            logger.error("HERMES_API_KEY not configured, skip brain push")
            return

        async with AsyncClient(timeout=60) as http:
            brain_resp = await http.post(
                hermes_url,
                headers={"Authorization": f"Bearer {hermes_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-v4-flash",
                    "messages": [
                        {"role": "system", "content": f"你是屿风回复助手，专为LGBTQ+交友平台提供客服支持。回复要温暖专业。\n\n以下是数据库中的相关上下文，请参考回复：\n{_build_db_context(user_message)}"},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            )
            if brain_resp.status_code != 200:
                logger.warning("Hermes brain %%d", brain_resp.status_code)
                return
            brain_data = brain_resp.json()
            brain_reply = brain_data["choices"][0]["message"]["content"]

        corp_id = getattr(settings, "WECOM_CORP_ID", "") or ""
        agent_id = getattr(settings, "WECOM_AGENT_ID", "") or ""
        app_secret = getattr(settings, "WECOM_APP_SECRET", "") or ""
        if not all([corp_id, agent_id, app_secret]):
            logger.error("missing WeCom push credentials")
            return

        async with AsyncClient(timeout=10) as http:
            tok_resp = await http.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={"corpid": corp_id, "corpsecret": app_secret},
            )
            tok_data = tok_resp.json()
            if tok_data.get("errcode") != 0:
                logger.warning("gettoken failed: %s", tok_data)
                return
            access_token = tok_data["access_token"]

        push_text = f"【Hermes 客服大脑】\\n{brain_reply}"
        async with AsyncClient(timeout=10) as http:
            push_resp = await http.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}",
                json={
                    "touser": from_user,
                    "msgtype": "text",
                    "agentid": int(agent_id) if agent_id else 0,
                    "text": {"content": push_text},
                    "safe": 0,
                },
            )
            push_data = push_resp.json()
            logger.info("active_send to=%s ok=%s resp=%s", from_user, push_data.get("errcode") == 0, push_data)

    except Exception:
        logger.error("async brain push failed", exc_info=True)



# ─── 消息处理（POST） ───────────────────────────────────────


def _parse_message_xml(xml_text: str) -> dict:
    """解析企微回调的 XML 消息"""
    root = ET.fromstring(xml_text)
    result = {}
    for child in root:
        result[child.tag] = child.text or ""
    return result


def _extract_customer_name(text: str) -> str | None:
    """模糊提取客户名：消息中提到微信名+链接/填表关键词即触发"""
    if not any(kw in text for kw in ["链接", "填表"]):
        return None

    # 非名字的常见词（过滤误触）
    NOT_NAME = {"这个", "那个", "哪个", "一个", "个", "什么", "发个",
                 "帮我", "给", "链接", "填表", "link",
                 "看看", "看看什么", "是不是可以", "是不是", "可以",
                 "麻烦", "给我"}
    NOT_NAME_SUB = {"这个", "那个", "哪个", "可以", "什么",
                     "看看", "是不是", "帮我", "麻烦"}

    m = re.search(
        r"(?:"
        r"给(.+?)发(?:个|个的|)?(?:填表)?链接"               # 给清风徐来发链接
        r"|给(.+?)(?:的)?(?:(?:填表)?链接|填表)"           # 给清风徐来链接/给清风徐来填表
        r"|发(.+?)(?:的)?(?:(?:填表)?链接|填表)"           # 发清风徐来链接/发清风徐来填表
        r"|(.{2,6})的(?:链接|填表)"                        # 清风徐来的链接
        r"|(.{2,4})\s*(?:链接|填表)"                       # 清风徐来链接 / 清风徐来填表（含空格）
        r")",
        text
    )
    if m:
        name = next(g for g in m.groups() if g)
        name = name.strip()
        # 验证：2-6字符，主要是汉字，不在排除列表
        chinese = re.findall(r"[\u4e00-\u9fff]", name)
        has_bad = any(sub in name for sub in NOT_NAME_SUB)
        if 2 <= len(name) <= 6 and len(chinese) >= len(name) - 1 and name not in NOT_NAME and not has_bad:
            return name
    return None


def _build_text_reply_xml(from_user: str, to_user: str, content: str) -> str:
    """构造文本回复的 XML"""
    create_time = int(time.time())
    return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{create_time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


@router.post("/callback")
async def wecom_callback_event(request: Request, db: Session = Depends(get_db)):
    """处理企微自建应用的消息回调

    目前支持：
    - 员工说「给清风徐来发填表链接」→ 自动生成链接并回复
    """
    body = await request.body()

    # ---------- 解密消息 ----------
    try:
        token, aes_key = _get_token_and_aes_key()
    except WecomCallbackError:
        return Response(content="success", media_type="text/plain; charset=utf-8")

    try:
        raw_xml = body.decode("utf-8")
        # 解析 <Encrypt> 标签
        enc_match = re.search(r"<Encrypt><!\[CDATA\[(.*?)\]\]></Encrypt>", raw_xml, re.DOTALL)
        if not enc_match:
            return Response(content="success", media_type="text/plain; charset=utf-8")

        encrypted = enc_match.group(1)

        # 解析 msg_signature 等信息
        sig_match = re.search(r"<MsgSignature><!\[CDATA\[(.*?)\]\]></MsgSignature>", raw_xml)
        ts_match = re.search(r"<TimeStamp>(.*?)</TimeStamp>", raw_xml)
        nonce_match = re.search(r"<Nonce><!\[CDATA\[(.*?)\]\]></Nonce>", raw_xml)

        if sig_match and ts_match and nonce_match:
            _verify_signature(token, ts_match.group(1), nonce_match.group(1), encrypted, sig_match.group(1))

        decrypted = _decrypt_message(encrypted, aes_key)
    except Exception:
        return Response(content="success", media_type="text/plain; charset=utf-8")

    # ---------- 解析消息 ----------
    try:
        msg = _parse_message_xml(decrypted)
    except Exception:
        return Response(content="success", media_type="text/plain; charset=utf-8")

    msg_type = msg.get("MsgType", "")
    content = msg.get("Content", "").strip()
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")  # 即自建应用的 AppID

    # ---------- 只处理文本消息 ----------
    if msg_type != "text" or not content:
        return Response(content="success", media_type="text/plain; charset=utf-8")

    # ---------- 检测「给XXX发链接」指令 ----------
    customer_name = _extract_customer_name(content)
    if customer_name and from_user:
        import uuid

        token_str = uuid.uuid4().hex
        link = RegistrationLink(
            token=token_str,
            employee_userid=from_user,
            customer_name=customer_name,
            status="pending",
        )
        db.add(link)
        db.commit()

        link_url = f"https://yufeng.team/api/wecom/tag/register-form?token={token_str}"

        reply_text = (
            f"✅ 已为「{customer_name}」生成专属登记链接：\n"
            f"{link_url}\n\n"
            f"把链接发给 {customer_name}，他填表后会自动打标签 📝"
        )
    else:
        # 其他消息 → 先快速回，后台调 Hermes 带 GBrain 主动推送
        asyncio.ensure_future(_async_hermes_brain_push(content, from_user))
        reply_text = "🤔 已收到，已提交 AI 大脑（含知识库）思考中，稍后推送完整回复..."

    # ---------- 加密回复 ----------
    try:
        reply_xml = _build_text_reply_xml(from_user, to_user, reply_text)
        encrypted_reply = _encrypt_reply(reply_xml, token, aes_key, settings.WECOM_CORP_ID)
        return Response(content=encrypted_reply, media_type="application/xml; charset=utf-8")
    except Exception:
        return Response(content="success", media_type="text/plain; charset=utf-8")


# ─── 数据库上下文注入 ─────────────────────────────────────

def _build_db_context(query: str) -> str:
    """根据用户问题查询数据库，返回上下文摘要"""
    from app.core.database import SessionLocal
    from sqlalchemy import text

    ctx_parts = []

    try:
        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT mp.nickname, mp.city, mp.age, mp.job, mp.income,
                           mp.role_self, mp.body_type, mp.lifestyle_status,
                           mp.hobbies, mp.current_situation, mp.expectation,
                           mp.long_distance
                    FROM member_profiles mp
                    WHERE mp.nickname ILIKE :q OR mp.city ILIKE :q
                       OR mp.job ILIKE :q OR mp.hobbies ILIKE :q
                       OR mp.lifestyle_status ILIKE :q
                    ORDER BY mp.updated_at DESC LIMIT 5
                """),
                {"q": f"%{query}%"}
            )
            members = rows.fetchall()
            if members:
                ctx_parts.append("【会员数据】最近匹配的会员：")
                for m in members:
                    ctx_parts.append(
                        f"  - {m.nickname or '匿名'} | {m.city or ''} | {m.age or ''}岁 | "
                        f"{m.job or ''} | 收入{m.income or ''} | 角色{m.role_self or ''} | "
                        f"体型{m.body_type or ''} | {m.long_distance or ''}"
                    )
        finally:
            db.close()
    except Exception as exc:
        ctx_parts.append(f"【会员查询异常】{exc}")

    try:
        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT title, start_time, location, max_participants
                    FROM events
                    WHERE status = 'approved' AND start_time >= NOW()
                    ORDER BY start_time ASC LIMIT 3
                """)
            )
            events = rows.fetchall()
            if events:
                ctx_parts.append("\n【近期活动】")
                for e in events:
                    ctx_parts.append(f"  - {e.title} | {e.start_time} | {e.location} | 名额{e.max_participants}")
        finally:
            db.close()
    except Exception as exc:
        ctx_parts.append(f"【活动查询异常】{exc}")

    return "\n".join(ctx_parts)

