"""
微信支付 v3 JSAPI 支付工具。

职责：
- 调用微信支付 JSAPI 下单接口生成 prepay_id
- 生成小程序 wx.requestPayment 需要的 RSA 签名参数
- 解密微信支付 v3 回调 resource

注意：真实支付必须在环境变量中配置：
WX_MCH_ID、WX_PAY_PRIVATE_KEY_PATH、WX_PAY_SERIAL_NO、WX_PAY_API_V3_KEY、WX_PAY_NOTIFY_URL。
"""
import base64
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


WECHAT_PAY_BASE_URL = "https://api.mch.weixin.qq.com"


class WechatPayConfigError(RuntimeError):
    pass


class WechatPayAPIError(RuntimeError):
    pass


def _load_private_key():
    private_key_path = getattr(settings, "WX_PAY_PRIVATE_KEY_PATH", "") or getattr(settings, "WX_PAY_CERT_PATH", "")
    if not private_key_path:
        raise WechatPayConfigError("未配置 WX_PAY_PRIVATE_KEY_PATH（商户 API 私钥路径）")
    try:
        with open(private_key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    except FileNotFoundError as exc:
        raise WechatPayConfigError(f"商户 API 私钥文件不存在: {private_key_path}") from exc
    except Exception as exc:
        raise WechatPayConfigError(f"商户 API 私钥读取失败: {exc}") from exc


def _rsa_sign(message: str) -> str:
    private_key = _load_private_key()
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _build_authorization(method: str, url_path: str, body: str, timestamp: str, nonce: str) -> str:
    serial_no = getattr(settings, "WX_PAY_SERIAL_NO", "")
    if not settings.WX_MCH_ID:
        raise WechatPayConfigError("未配置 WX_MCH_ID（微信支付商户号）")
    if not serial_no:
        raise WechatPayConfigError("未配置 WX_PAY_SERIAL_NO（商户 API 证书序列号）")
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
    signature = _rsa_sign(message)
    return (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{settings.WX_MCH_ID}",'
        f'nonce_str="{nonce}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{serial_no}"'
    )


def _require_payment_config() -> None:
    missing = []
    for key in ["WX_APPID", "WX_MCH_ID", "WX_PAY_SERIAL_NO", "WX_PAY_API_V3_KEY", "WX_PAY_NOTIFY_URL"]:
        if not getattr(settings, key, ""):
            missing.append(key)
    private_key_path = getattr(settings, "WX_PAY_PRIVATE_KEY_PATH", "") or getattr(settings, "WX_PAY_CERT_PATH", "")
    if not private_key_path:
        missing.append("WX_PAY_PRIVATE_KEY_PATH")
    if missing:
        raise WechatPayConfigError("微信支付配置不完整: " + ", ".join(missing))


async def create_jsapi_prepay(
    *,
    out_trade_no: str,
    description: str,
    amount_total: int,
    payer_openid: str,
    attach: Optional[str] = None,
) -> Dict[str, Any]:
    """创建微信支付 JSAPI 预支付订单。amount_total 单位为分。"""
    _require_payment_config()
    if amount_total <= 0:
        raise WechatPayConfigError("支付金额必须大于 0 分")
    if not payer_openid:
        raise WechatPayConfigError("当前用户缺少 openid，无法发起小程序支付")

    url_path = "/v3/pay/transactions/jsapi"
    payload: Dict[str, Any] = {
        "appid": settings.WX_APPID,
        "mchid": settings.WX_MCH_ID,
        "description": description[:127] or "屿风活动报名",
        "out_trade_no": out_trade_no,
        "notify_url": settings.WX_PAY_NOTIFY_URL,
        "amount": {"total": amount_total, "currency": "CNY"},
        "payer": {"openid": payer_openid},
    }
    if attach:
        payload["attach"] = attach[:127]

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    timestamp = str(int(datetime.now().timestamp()))
    nonce = uuid.uuid4().hex
    headers = {
        "Authorization": _build_authorization("POST", url_path, body, timestamp, nonce),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "yufeng-event-api/1.0",
    }

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(WECHAT_PAY_BASE_URL + url_path, content=body.encode("utf-8"), headers=headers)
    if resp.status_code < 200 or resp.status_code >= 300:
        raise WechatPayAPIError(f"微信支付下单失败({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def build_request_payment_params(prepay_id: str) -> Dict[str, str]:
    """生成 wx.requestPayment 所需参数。"""
    if not prepay_id:
        raise WechatPayConfigError("缺少 prepay_id")
    timestamp = str(int(datetime.now().timestamp()))
    nonce = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    message = f"{settings.WX_APPID}\n{timestamp}\n{nonce}\n{package}\n"
    return {
        "timeStamp": timestamp,
        "timestamp": timestamp,
        "nonceStr": nonce,
        "nonce_str": nonce,
        "package": package,
        "signType": "RSA",
        "sign_type": "RSA",
        "paySign": _rsa_sign(message),
        "sign": _rsa_sign(message),
        "prepay_id": prepay_id,
    }


def decrypt_notify_resource(resource: Dict[str, Any]) -> Dict[str, Any]:
    """解密微信支付 v3 回调 resource。"""
    api_v3_key = getattr(settings, "WX_PAY_API_V3_KEY", "") or getattr(settings, "WX_PAY_KEY", "")
    if not api_v3_key:
        raise WechatPayConfigError("未配置 WX_PAY_API_V3_KEY")
    try:
        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        nonce = resource["nonce"].encode("utf-8")
        ciphertext = base64.b64decode(resource["ciphertext"])
        associated_data = (resource.get("associated_data") or "").encode("utf-8")
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise WechatPayConfigError(f"微信支付回调解密失败: {exc}") from exc
