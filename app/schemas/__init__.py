"""
Pydantic 数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ====== 用户 + 认证 ======

class MatchWelcomeMessage(BaseModel):
    title: str = "欢迎入群"
    content: str = ""


class MatchGroupConfig(BaseModel):
    status: str = "pending"
    chatid: str = ""
    open_chat_supported: bool = False
    open_chat_method: str = ""
    open_chat_payload: str = ""
    fallback_qr_url: str = ""
    fallback_reason: str = ""
    invite_title: str = ""
    invite_subtitle: str = ""
    invite_code: str = ""
    invite_tips: List[str] = Field(default_factory=list)
    share_message: str = ""
    share_link: str = ""
    qr_expires_at: str = ""
    welcome_message: MatchWelcomeMessage = Field(default_factory=MatchWelcomeMessage)


class MatchRecordInfo(BaseModel):
    id: str
    nickname: str = ""
    age: int = 0
    city: str = ""
    match_type: str = "AI红娘"
    match_type_key: str = "ai"
    match_time: str = ""
    status: str = "进行中"
    status_key: str = "ongoing"
    summary: str = ""
    score: int = 0
    group_config: Optional[MatchGroupConfig] = None


class PointsHistoryItem(BaseModel):
    type: str = ""
    points: str = ""
    date: str = ""
    icon: str = ""


class UserInfo(BaseModel):
    id: int
    user_no: str = ""
    nickname: str
    avatar_url: str
    avatar: str = ""  # alias for avatar_url, frontend compatibility
    phone: str = ""
    age: int = 0
    city: str = ""
    points: int = 0
    member_level: int = 0
    test_remaining: int = 3
    is_organizer: bool
    organizer_verified: bool
    role_tag: str = ""
    personality_tag: str = ""
    subtitle: str = ""
    points_history: List[PointsHistoryItem] = Field(default_factory=list)
    match_records: List[MatchRecordInfo] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WxLoginRequest(BaseModel):
    code: str
    nickname: str = ""
    avatar_url: str = ""


class WxLoginResponse(BaseModel):
    token: str
    user: UserInfo


class ProfileUpdateRequest(BaseModel):
    nickname: str = Field("", max_length=50)
    avatar_url: str = Field("", max_length=500)
    phone: str = Field("", max_length=20)
    city: str = Field("", max_length=50)
    age: int = 0


class CertApplyRequest(BaseModel):
    real_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=5, max_length=20)
    id_card: str = Field("", max_length=30)
    qualification: List[str] = Field(default=[], description="资质证明图片URL数组")
    intro: str = Field("", max_length=500)


class CertInfo(BaseModel):
    id: int
    user_id: int
    real_name: str
    phone: str
    id_card: str
    qualification: list
    intro: str
    status: str
    reject_reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class CertReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    reject_reason: str = ""


# ====== 活动 ======

class RegistrationFormField(BaseModel):
    id: str = ""
    label: str = ""
    required: bool = False
    enabled: bool = True


class RegistrationFormQuestion(BaseModel):
    id: str = ""
    type: str = "输入"
    title: str = ""
    required: bool = False


class RegistrationFormSchema(BaseModel):
    enabledFields: List[RegistrationFormField] = Field(default=[])
    customQuestions: List[RegistrationFormQuestion] = Field(default=[])


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    category: str = "其他"
    cover_image: str = ""
    images: List[str] = []
    registration_form: Optional[RegistrationFormSchema] = None
    location_name: str = ""
    address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    max_participants: Optional[int] = None
    price: float = 0


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[List[str]] = None
    registration_form: Optional[RegistrationFormSchema] = None
    location_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    max_participants: Optional[int] = None
    price: Optional[float] = None


class EventInfo(BaseModel):
    id: int
    title: str
    description: str
    category: str
    cover_image: str
    images: list
    registration_form: RegistrationFormSchema = Field(default_factory=RegistrationFormSchema)
    location_name: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    max_participants: Optional[int] = None
    price: float
    status: str
    publisher_id: int
    publisher: Optional[UserInfo] = None
    view_count: int
    favorite_count: int
    share_count: int
    is_favorited: bool = False
    is_registered: bool = False
    registrant_count: int = 0
    is_official: bool = False
    created_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventListItem(BaseModel):
    id: int
    title: str
    category: str
    cover_image: str
    location_name: str
    start_time: datetime
    price: float
    status: str
    max_participants: Optional[int] = None
    registered_count: int = 0  # alias for registrant_count, frontend compatibility
    publisher_nickname: str = ""
    publisher_avatar: str = ""
    registrant_count: int = 0
    favorite_count: int
    is_favorited: bool = False
    is_official: bool = False

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    items: List[EventListItem]
    total: int
    page: int
    page_size: int


# ====== 报名 & 支付 ======

class RegisterRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=10)
    remark: str = ""


class PayRequest(BaseModel):
    registration_id: int


class PayResponse(BaseModel):
    prepay_id: str
    package: str          # 微信支付参数
    nonce_str: str
    timestamp: str
    sign: str


class RegistrationInfo(BaseModel):
    id: int
    event_id: int
    event_title: str = ""
    status: str
    ticket_code: Optional[str] = None
    quantity: int
    total_price: float
    payment_id: str
    paid_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    remark: str
    created_at: datetime

    class Config:
        from_attributes = True


class TicketInfo(BaseModel):
    registration_id: int
    event_id: int
    event_title: str
    event_start_time: datetime
    event_location: str
    user_id: int
    user_nickname: str
    status: str
    ticket_code: str
    quantity: int
    payment_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ====== 收藏 ======

class FavoriteToggleResponse(BaseModel):
    is_favorited: bool
    favorite_count: int


# ====== 管理员 ======

class CommissionConfig(BaseModel):
    rate: float = Field(..., ge=0, le=100)
    min_fee: float = 0
    max_fee: Optional[float] = None


# ====== 通用 ======

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """通用分页响应包装器"""
    items: list
    total: int
    page: int
    page_size: int


# ====== 合作推广申请 ======


class CooperationApplyRequest(BaseModel):
    """小程序提交合作推广申请"""
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    wechat: str = Field("", max_length=100)
    resource_type: str = Field("", max_length=100)
    resource_name: str = Field("", max_length=200)
    resource_desc: str = Field("", max_length=2000)
    followers: str = Field("", max_length=50)
    coop_intent: str = Field("", max_length=2000)


class CooperationApplicationInfo(BaseModel):
    """合作推广申请详情"""
    id: int
    user_id: Optional[int] = None
    name: str
    phone: str
    wechat: str = ""
    resource_type: str = ""
    resource_name: str = ""
    resource_desc: str = ""
    followers: str = ""
    coop_intent: str = ""
    status: str = "pending"
    admin_note: str = ""
    follow_up_at: Optional[datetime] = None
    follow_up_count: int = 0
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reject_reason: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CooperationReviewRequest(BaseModel):
    """审核合作推广申请"""
    action: str = Field(..., pattern="^(approve|reject|close)$")
    reject_reason: str = ""


class CooperationNoteUpdate(BaseModel):
    """更新管理员备注"""
    admin_note: str = ""


class CooperationFollowUpUpdate(BaseModel):
    """记录跟进"""
    follow_up_at: Optional[datetime] = None
