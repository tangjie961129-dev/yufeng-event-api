"""
屿风活动报名小程序 - 配置文件
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "屿风活动报名"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "postgresql://gbrain:***@localhost:5432/yufeng"
    DB_POOL_SIZE: int = 10

    # JWT
    SECRET_KEY: str = "yufeng-event-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # 微信小程序
    WX_APPID: str = "wx161b14b55c8df8ff"
    WX_SECRET: str = ""  # 需要在 .env 中设置
    WX_LOGIN_URL: str = "https://api.weixin.qq.com/sns/jscode2session"

    # 微信支付
    WX_MCH_ID: str = ""  # 实际值由 .env 覆盖
    # API v3 key；兼容旧变量 WX_PAY_KEY
    WX_PAY_API_V3_KEY: str = ""
    WX_PAY_KEY: str = ""
    # 商户 API 私钥路径（apiclient_key.pem）；兼容旧变量 WX_PAY_CERT_PATH
    WX_PAY_PRIVATE_KEY_PATH: str = ""
    WX_PAY_CERT_PATH: str = ""
    # 商户 API 证书序列号
    WX_PAY_SERIAL_NO: str = ""
    WX_PAY_NOTIFY_URL: str = "https://yufeng.team/api/payment/notify"

    # 企微群聊配置
    WECOM_AGENT_ID: str = ""
    WECOM_CORP_ID: str = ""
    WECOM_SECRET: str = ""
    WECOM_APP_SECRET: str = ""
    WECOM_GROUP_FALLBACK_QR_URL: str = ""
    WECOM_GROUP_INVITE_LINK: str = ""
    WECOM_GROUP_INVITE_TITLE: str = "屿风匹配沟通群"
    WECOM_GROUP_INVITE_SUBTITLE: str = "扫码入群后先看欢迎消息，再完成第一句破冰"
    WECOM_REAL_GROUP_ENTRY_URL: str = ""
    WECOM_REAL_GROUP_QR_URL: str = ""
    WECOM_GROUP_JOIN_WAY_ID: str = ""
    WECOM_API_BASE: str = "https://qyapi.weixin.qq.com"

    # 微信客服/企业微信回调 URL 验证
    WX_KF_TOKEN: str = ""
    WX_KF_ENCODING_AES_KEY: str = ""
    WECOM_TOKEN: str = ""
    WECOM_ENCODING_AES_KEY: str = ""

    # AI / OpenAI-compatible customer assistant
    # OPENAI_* is used by wx_kf.py for the fast WeCom assistant path; keep these
    # declared because Settings.Config.extra=ignore drops undeclared .env keys.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://99887123.xyz/v1"
    CUSTOMER_ASSISTANT_MODEL: str = "gpt-5.5"

    # DeepSeek AI
    DEEPSEEK_API_KEY: str = ""

    # 上传文件
    UPLOAD_DIR: str = "/data/yufeng-uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
