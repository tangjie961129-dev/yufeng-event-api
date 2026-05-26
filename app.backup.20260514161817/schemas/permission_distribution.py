"""
权限管理与分销系统 Schema
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class PermissionItem(BaseModel):
    key: str
    name: str


class AdminPermissionMeResponse(BaseModel):
    role: str
    permissions: List[PermissionItem]


class AdminAccountItem(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None


class AdminAccountListResponse(BaseModel):
    items: List[AdminAccountItem]
    total: int
    page: int
    page_size: int


class AdminAccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: str = Field(default="管理员", max_length=100)
    role: str = Field(default="operator", max_length=30)


class AdminAccountToggleRequest(BaseModel):
    is_active: bool


class DistributorListItem(BaseModel):
    id: int
    user_id: int
    nickname: str
    phone: str
    invite_code: str
    display_name: str
    level: str
    status: str
    referrer_user_id: Optional[int] = None
    total_invited_users: int
    total_paid_orders: int
    total_commission_earned: float
    withdrawable_balance: float
    approved_at: Optional[str] = None
    created_at: Optional[str] = None


class DistributorListResponse(BaseModel):
    items: List[DistributorListItem]
    total: int
    page: int
    page_size: int


class CommissionLedgerItem(BaseModel):
    id: int
    distributor_user_id: int
    distributor_name: str
    invited_user_id: Optional[int] = None
    invited_user_name: str = ""
    event_registration_id: Optional[int] = None
    source_type: str
    status: str
    amount: float
    rate: float
    note: str
    created_at: Optional[str] = None
    settled_at: Optional[str] = None


class CommissionLedgerListResponse(BaseModel):
    items: List[CommissionLedgerItem]
    total: int
    page: int
    page_size: int


class WithdrawalRequestItem(BaseModel):
    id: int
    distributor_user_id: int
    distributor_name: str
    amount: float
    account_name: str
    account_type: str
    account_no: str
    status: str
    reject_reason: str
    reviewed_by_admin_id: Optional[int] = None
    reviewed_admin_name: str = ""
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    paid_at: Optional[str] = None


class WithdrawalRequestListResponse(BaseModel):
    items: List[WithdrawalRequestItem]
    total: int
    page: int
    page_size: int


class WithdrawalReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|paid)$")
    reject_reason: str = Field(default="", max_length=200)


class RoleListItem(BaseModel):
    id: int
    code: str
    name: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RoleListResponse(BaseModel):
    items: List[RoleListItem]
    total: int


class PermissionListItem(BaseModel):
    id: int
    code: str
    name: str
    module: str
    action: str
    created_at: Optional[str] = None


class PermissionListResponse(BaseModel):
    items: List[PermissionListItem]
    total: int


class UserRoleBindingItem(BaseModel):
    id: int
    principal_type: str
    principal_id: int
    role_code: str
    source: str
    status: str
    granted_by: Optional[int] = None
    granted_at: Optional[str] = None
    revoked_by: Optional[int] = None
    revoked_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserRoleBindingListResponse(BaseModel):
    items: List[UserRoleBindingItem]
    total: int


class DataScopeItem(BaseModel):
    id: int
    role_code: str
    scope_code: str
    resource_type: str
    config_json: Any
    created_at: Optional[str] = None


class DataScopeListResponse(BaseModel):
    items: List[DataScopeItem]
    total: int


class OrganizerProfileItem(BaseModel):
    id: int
    user_id: int
    nickname: str
    phone: str
    status: str
    brand_name: str
    city: str
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    note: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OrganizerProfileListResponse(BaseModel):
    items: List[OrganizerProfileItem]
    total: int
    page: int
    page_size: int


class AgentProfileItem(BaseModel):
    id: int
    user_id: int
    nickname: str
    phone: str
    agent_code: str
    level: str
    status: str
    identity_label: str
    bind_channel: str
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    reject_reason: str
    note: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentProfileListResponse(BaseModel):
    items: List[AgentProfileItem]
    total: int
    page: int
    page_size: int


class ReferralBindingItem(BaseModel):
    id: int
    invited_user_id: int
    invited_user_name: str
    inviter_user_id: int
    inviter_user_name: str
    inviter_type: str
    binding_type: str
    source_channel: str
    source_code: str
    campaign_code: str
    landing_page: str
    status: str
    first_order_registration_id: Optional[int] = None
    invalid_reason: str
    idempotency_key: str
    bound_at: Optional[str] = None
    locked_at: Optional[str] = None
    invalidated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReferralBindingListResponse(BaseModel):
    items: List[ReferralBindingItem]
    total: int
    page: int
    page_size: int


class RevenueShareRuleItem(BaseModel):
    id: int
    target_type: str
    target_id: int
    target_name_snapshot: str
    agent_level: str
    commission_mode: str
    commission_rate: Optional[float] = None
    commission_amount: Optional[float] = None
    effective_status: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RevenueShareRuleListResponse(BaseModel):
    items: List[RevenueShareRuleItem]
    total: int
    page: int
    page_size: int


class AgentCommissionLedgerItem(BaseModel):
    id: int
    agent_user_id: int
    agent_name: str
    invited_user_id: int
    invited_user_name: str
    binding_id: int
    order_type: str
    source_order_id: str
    source_registration_id: Optional[int] = None
    owner_type_snapshot: str
    product_type_snapshot: str
    target_name_snapshot: str
    base_amount: float
    commission_rate: Optional[float] = None
    commission_amount: float
    settlement_status: str
    settlement_batch_no: str
    rule_id: Optional[int] = None
    business_key: str
    occurred_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    settled_at: Optional[str] = None
    reversed_at: Optional[str] = None
    reverse_reason: str
    idempotency_key: str
    note: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentCommissionLedgerListResponse(BaseModel):
    items: List[AgentCommissionLedgerItem]
    total: int
    page: int
    page_size: int


class UserReferralRewardLedgerItem(BaseModel):
    id: int
    inviter_user_id: int
    inviter_user_name: str
    invited_user_id: int
    invited_user_name: str
    binding_id: int
    first_order_registration_id: Optional[int] = None
    reward_type: str
    reward_amount_cash: float
    reward_amount_points: int
    reward_amount_coupon: int
    reward_status: str
    eligible_biz_type: str
    eligible_product_type: str
    owner_type_snapshot: str
    product_type_snapshot: str
    target_name_snapshot: str
    rule_id: Optional[int] = None
    business_key: str
    granted_at: Optional[str] = None
    reversed_at: Optional[str] = None
    reverse_reason: str
    idempotency_key: str
    note: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserReferralRewardLedgerListResponse(BaseModel):
    items: List[UserReferralRewardLedgerItem]
    total: int
    page: int
    page_size: int


class AgentWalletAccountItem(BaseModel):
    id: int
    user_id: int
    user_name: str
    account_type: str
    total_earned: float
    total_settled: float
    total_withdrawn: float
    withdrawable_balance: float
    frozen_balance: float
    updated_at: Optional[str] = None


class AgentWalletAccountListResponse(BaseModel):
    items: List[AgentWalletAccountItem]
    total: int
    page: int
    page_size: int


class AgentWithdrawalRequestItem(BaseModel):
    id: int
    agent_user_id: int
    agent_name: str
    amount: float
    account_name: str
    account_type: str
    account_no: str
    status: str
    reviewed_by: Optional[int] = None
    reviewed_admin_name: str = ""
    reviewed_at: Optional[str] = None
    paid_at: Optional[str] = None
    reject_reason: str
    idempotency_key: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AgentWithdrawalRequestListResponse(BaseModel):
    items: List[AgentWithdrawalRequestItem]
    total: int
    page: int
    page_size: int


class AuditLogItem(BaseModel):
    id: int
    actor_type: str
    actor_id: Optional[int] = None
    action_code: str
    target_type: str
    target_id: str
    biz_type: str
    request_id: str
    idempotency_key: str
    remark: str
    ip: str
    user_agent: str
    created_at: Optional[str] = None


class AuditLogListResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    page_size: int


class IdempotencyRecordItem(BaseModel):
    id: int
    biz_type: str
    biz_key: str
    idempotency_key: str
    request_hash: str
    status: str
    expired_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IdempotencyRecordListResponse(BaseModel):
    items: List[IdempotencyRecordItem]
    total: int
    page: int
    page_size: int


class ReferralBindingCreateRequest(BaseModel):
    inviter_user_id: int = Field(..., ge=1)
    inviter_type: str = Field(..., pattern="^(agent|user)$")
    binding_type: str = Field(..., pattern="^(agent_referral|first_order_reward)$")
    source_channel: str = Field(default="referrer_id", pattern="^(mini_program|link|qr_code|referrer_id)$")
    source_code: str = Field(default="", max_length=100)
    landing_page: str = Field(default="", max_length=255)
    campaign_code: str = Field(default="", max_length=100)
    binding_context_json: Any = Field(default_factory=dict)
    idempotency_key: str = Field(..., min_length=8, max_length=100)


class RevenueShareRuleCreateRequest(BaseModel):
    target_type: str = Field(..., pattern="^(official_product|official_event)$")
    target_id: int = Field(..., ge=1)
    target_name_snapshot: str = Field(default="", max_length=200)
    agent_level: str = Field(default="level_1", max_length=30)
    commission_mode: str = Field(default="fixed_rate", pattern="^(fixed_rate|fixed_amount)$")
    commission_rate: Optional[float] = Field(default=None, ge=0, le=100)
    commission_amount: Optional[float] = Field(default=None, ge=0)
    effective_status: str = Field(default="active", pattern="^(active|inactive)$")
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class RevenueShareRuleUpdateRequest(BaseModel):
    target_name_snapshot: Optional[str] = Field(default=None, max_length=200)
    agent_level: Optional[str] = Field(default=None, max_length=30)
    commission_mode: Optional[str] = Field(default=None, pattern="^(fixed_rate|fixed_amount)$")
    commission_rate: Optional[float] = Field(default=None, ge=0, le=100)
    commission_amount: Optional[float] = Field(default=None, ge=0)
    effective_status: Optional[str] = Field(default=None, pattern="^(active|inactive)$")
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class ReferralBindingStatusUpdateRequest(BaseModel):
    action: str = Field(..., pattern="^(lock|invalidate)$")
    invalid_reason: str = Field(default="", max_length=200)


class AgentWithdrawalCreateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    account_name: str = Field(..., min_length=1, max_length=100)
    account_type: str = Field(default="wechat", max_length=30)
    account_no: str = Field(..., min_length=1, max_length=100)
    idempotency_key: str = Field(..., min_length=8, max_length=100)


class AgentWithdrawalReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|paid)$")
    reject_reason: str = Field(default="", max_length=200)
