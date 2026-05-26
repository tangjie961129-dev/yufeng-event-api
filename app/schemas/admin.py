"""
管理员相关 Schema
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class AdminUserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class AdminLoginResponse(BaseModel):
    token: str
    user: AdminUserInfo


class DashboardOverview(BaseModel):
    total_users: int
    total_organizers: int
    total_events: int
    pending_events: int
    pending_certs: int
    total_registrations: int
    paid_orders: int
    total_revenue: float
    total_commission: float


class TrendItem(BaseModel):
    date: str
    registrations: int
    revenue: float


class DashboardTrendResponse(BaseModel):
    items: List[TrendItem]


class AdminUserListItem(BaseModel):
    id: int
    nickname: str
    phone: str
    is_organizer: bool
    organizer_verified: bool
    created_at: Optional[str] = None


class AdminUserListResponse(BaseModel):
    items: List[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminOrderItem(BaseModel):
    id: int
    event_id: int
    event_title: str
    user_id: int
    user_nickname: str
    organizer_id: int
    organizer_name: str
    status: str
    quantity: int
    total_price: float
    payment_method: str
    payment_id: str
    commission_rate: float
    commission_amount: float
    paid_at: Optional[str] = None
    created_at: Optional[str] = None
    remark: str = ""


class AdminOrderListResponse(BaseModel):
    items: List[AdminOrderItem]
    total: int
    page: int
    page_size: int


class UiThemeConfig(BaseModel):
    primary_color: str = '#7c3aed'
    accent_color: str = '#ec4899'
    text_color: str = '#111827'
    page_background: str = '#f8fafc'
    card_radius: int = 20

    @field_validator('card_radius', mode='before')
    @classmethod
    def validate_card_radius(cls, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return 20
        return max(0, min(40, value))


class UiBannerItem(BaseModel):
    id: str = ''
    title: str = ''
    subtitle: str = ''
    image_url: str = ''
    target: str = ''
    enabled: bool = True
    sort_order: int = 0


class UiFeatureItem(BaseModel):
    key: str
    title: str
    description: str = ''
    icon: str = ''
    color: str = 'blue'
    enabled: bool = True
    sort_order: int = 0


class UiTabItem(BaseModel):
    key: str
    label: str
    icon: str = 'apps-o'
    page_path: str = ''
    enabled: bool = True
    sort_order: int = 0


class UiModuleConfig(BaseModel):
    show_notice: bool = True
    show_banners: bool = True
    show_categories: bool = True
    show_contact: bool = True
    show_feature_labels: bool = True
    show_tabbar: bool = True


class UiHomeConfig(BaseModel):
    hero_title: str = '屿风活动报名'
    hero_subtitle: str = '发现真实、温暖、有质感的同城活动'
    hero_image: str = ''
    announcement: str = ''
    show_banner: bool = True


class UiContactConfig(BaseModel):
    service_wechat: str = ''
    service_phone: str = ''
    service_email: str = ''


class AdminUiConfigPayload(BaseModel):
    home: UiHomeConfig = Field(default_factory=UiHomeConfig)
    theme: UiThemeConfig = Field(default_factory=UiThemeConfig)
    contact: UiContactConfig = Field(default_factory=UiContactConfig)
    modules: UiModuleConfig = Field(default_factory=UiModuleConfig)
    banners: List[UiBannerItem] = Field(default_factory=list)
    features: List[UiFeatureItem] = Field(default_factory=list)
    tabs: List[UiTabItem] = Field(default_factory=list)
    tabbar: List[UiTabItem] = Field(default_factory=list)


class AdminUiConfigResponse(AdminUiConfigPayload):
    pass


# ====== 管理员账号管理 ======


class AdminAccountDetail(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    wechat_openid: Optional[str] = None
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AdminAccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: str = "管理员"
    role: str = "admin"


class AdminBindWechatRequest(BaseModel):
    openid: str = Field(..., min_length=1, description="微信小程序用户的openid")
