"""
权限管理与分销系统正式版（含 P0 兼容）数据模型
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    DECIMAL,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.core.database import Base


class AdminRolePermission(Base):
    """后台角色权限映射（轻量版 P0）"""
    __tablename__ = "admin_role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False, index=True)
    permission_key = Column(String(100), nullable=False, index=True)
    permission_name = Column(String(100), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role", "permission_key", name="uq_admin_role_permission"),
    )


class Role(Base):
    """正式角色定义"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(30), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Permission(Base):
    """正式权限点定义"""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    module = Column(String(50), default="")
    action = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    """角色与权限映射"""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_code = Column(String(50), nullable=False, index=True)
    permission_code = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role_code", "permission_code", name="uq_role_permission"),
    )


class UserRoleBinding(Base):
    """用户/后台账号角色绑定"""
    __tablename__ = "user_role_bindings"

    id = Column(Integer, primary_key=True, index=True)
    principal_type = Column(String(30), nullable=False, index=True)
    principal_id = Column(Integer, nullable=False, index=True)
    role_code = Column(String(50), nullable=False, index=True)
    source = Column(String(30), default="system", index=True)
    status = Column(String(30), default="active", index=True)
    granted_by = Column(Integer, nullable=True)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "principal_type",
            "principal_id",
            "role_code",
            name="uq_principal_role_binding",
        ),
    )


class DataScope(Base):
    """数据权限范围定义"""
    __tablename__ = "data_scopes"

    id = Column(Integer, primary_key=True, index=True)
    role_code = Column(String(50), nullable=False, index=True)
    scope_code = Column(String(30), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    config_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role_code", "scope_code", "resource_type", name="uq_role_scope_resource"),
    )


class OrganizerProfile(Base):
    """主理人档案"""
    __tablename__ = "organizer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    status = Column(String(30), default="pending", index=True)
    brand_name = Column(String(100), default="")
    city = Column(String(50), default="")
    approved_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentProfile(Base):
    """一级代理/共享合伙人档案"""
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    agent_code = Column(String(32), nullable=False, unique=True, index=True)
    level = Column(String(30), default="level_1", index=True)
    status = Column(String(30), default="pending", index=True)
    approved_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    reject_reason = Column(Text, default="")
    bind_channel = Column(String(30), default="")
    identity_label = Column(String(50), default="共享合伙人")
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReferralBinding(Base):
    """邀请绑定关系（B 规则：同一被邀请人只能命中一种有效关系）"""
    __tablename__ = "referral_bindings"

    id = Column(Integer, primary_key=True, index=True)
    invited_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    inviter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    inviter_type = Column(String(30), nullable=False, index=True)
    binding_type = Column(String(30), nullable=False, index=True)
    source_channel = Column(String(30), default="referrer_id", index=True)
    source_code = Column(String(100), default="")
    landing_page = Column(String(255), default="")
    campaign_code = Column(String(100), default="")
    binding_context_json = Column(Text, default="{}")
    status = Column(String(30), default="pending", index=True)
    first_order_registration_id = Column(Integer, ForeignKey("event_registrations.id"), nullable=True, index=True)
    bound_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    invalid_reason = Column(Text, default="")
    idempotency_key = Column(String(100), default="", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RevenueShareRule(Base):
    """官方商品/官方活动分润规则"""
    __tablename__ = "revenue_share_rules"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String(30), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    target_name_snapshot = Column(String(200), default="")
    agent_level = Column(String(30), default="level_1", index=True)
    commission_mode = Column(String(30), default="fixed_rate", index=True)
    commission_rate = Column(DECIMAL(5, 2), nullable=True)
    commission_amount = Column(DECIMAL(10, 2), nullable=True)
    effective_status = Column(String(30), default="active", index=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentCommissionLedger(Base):
    """一级代理长期返佣账本"""
    __tablename__ = "agent_commission_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    agent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invited_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    binding_id = Column(Integer, ForeignKey("referral_bindings.id"), nullable=False, index=True)
    order_type = Column(String(30), default="official_event", index=True)
    source_order_id = Column(String(100), default="", index=True)
    source_registration_id = Column(Integer, ForeignKey("event_registrations.id"), nullable=True, index=True)
    owner_type_snapshot = Column(String(30), default="official", index=True)
    product_type_snapshot = Column(String(50), default="")
    target_name_snapshot = Column(String(200), default="")
    base_amount = Column(DECIMAL(10, 2), default=0)
    commission_rate = Column(DECIMAL(5, 2), nullable=True)
    commission_amount = Column(DECIMAL(10, 2), default=0)
    settlement_status = Column(String(30), default="pending", index=True)
    settlement_batch_no = Column(String(100), default="")
    rule_id = Column(Integer, ForeignKey("revenue_share_rules.id"), nullable=True)
    rule_snapshot_json = Column(Text, default="{}")
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    reversed_at = Column(DateTime(timezone=True), nullable=True)
    reverse_reason = Column(Text, default="")
    reverse_ref_id = Column(Integer, nullable=True)
    idempotency_key = Column(String(100), default="", index=True)
    business_key = Column(String(100), nullable=False, unique=True, index=True)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserReferralRewardLedger(Base):
    """普通用户一级首单奖励账本（仅 AI 匹配会员首单）"""
    __tablename__ = "user_referral_reward_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    inviter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invited_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    binding_id = Column(Integer, ForeignKey("referral_bindings.id"), nullable=False, index=True)
    first_order_registration_id = Column(Integer, ForeignKey("event_registrations.id"), nullable=True, index=True)
    reward_type = Column(String(30), default="cash", index=True)
    reward_amount_cash = Column(DECIMAL(10, 2), default=0)
    reward_amount_points = Column(Integer, default=0)
    reward_amount_coupon = Column(Integer, default=0)
    reward_status = Column(String(30), default="pending", index=True)
    eligible_biz_type = Column(String(50), default="ai_match_membership_purchase", index=True)
    eligible_product_type = Column(String(50), default="ai_match_membership", index=True)
    owner_type_snapshot = Column(String(30), default="official", index=True)
    product_type_snapshot = Column(String(50), default="ai_match_membership")
    target_name_snapshot = Column(String(200), default="AI 匹配会员")
    rule_id = Column(Integer, ForeignKey("revenue_share_rules.id"), nullable=True)
    rule_snapshot_json = Column(Text, default="{}")
    granted_at = Column(DateTime(timezone=True), nullable=True)
    reversed_at = Column(DateTime(timezone=True), nullable=True)
    reverse_reason = Column(Text, default="")
    reverse_ref_id = Column(Integer, nullable=True)
    idempotency_key = Column(String(100), default="", index=True)
    business_key = Column(String(100), nullable=False, unique=True, index=True)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentWalletAccount(Base):
    """代理可提现余额账户"""
    __tablename__ = "agent_wallet_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    account_type = Column(String(30), default="agent_commission", index=True)
    total_earned = Column(DECIMAL(10, 2), default=0)
    total_settled = Column(DECIMAL(10, 2), default=0)
    total_withdrawn = Column(DECIMAL(10, 2), default=0)
    withdrawable_balance = Column(DECIMAL(10, 2), default=0)
    frozen_balance = Column(DECIMAL(10, 2), default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentWithdrawalRequest(Base):
    """一级代理提现申请"""
    __tablename__ = "agent_withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    agent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0)
    account_name = Column(String(100), default="")
    account_type = Column(String(30), default="wechat")
    account_no = Column(String(100), default="")
    status = Column(String(30), default="pending", index=True)
    reviewed_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    reject_reason = Column(Text, default="")
    idempotency_key = Column(String(100), default="", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_type = Column(String(30), nullable=False, index=True)
    actor_id = Column(Integer, nullable=True, index=True)
    action_code = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), default="", index=True)
    target_id = Column(String(100), default="", index=True)
    biz_type = Column(String(30), nullable=False, index=True)
    before_json = Column(Text, default="{}")
    after_json = Column(Text, default="{}")
    request_id = Column(String(100), default="", index=True)
    idempotency_key = Column(String(100), default="", index=True)
    remark = Column(Text, default="")
    ip = Column(String(64), default="")
    user_agent = Column(String(255), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    """关键请求幂等记录"""
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True)
    biz_type = Column(String(50), nullable=False, index=True)
    biz_key = Column(String(100), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=False, unique=True, index=True)
    request_hash = Column(String(128), default="")
    status = Column(String(30), default="processing", index=True)
    response_snapshot = Column(Text, default="{}")
    expired_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DistributorProfile(Base):
    """分销员/代理档案（P0 兼容旧表）"""
    __tablename__ = "distributor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    invite_code = Column(String(32), nullable=False, unique=True, index=True)
    display_name = Column(String(100), default="")
    level = Column(String(30), default="basic", index=True)
    status = Column(String(30), default="pending", index=True)
    referrer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    total_invited_users = Column(Integer, default=0)
    total_paid_orders = Column(Integer, default=0)
    total_commission_earned = Column(DECIMAL(10, 2), default=0)
    withdrawable_balance = Column(DECIMAL(10, 2), default=0)
    notes = Column(Text, default="")
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DistributorInvite(Base):
    """邀请关系/绑定记录（P0 兼容旧表）"""
    __tablename__ = "distributor_invites"

    id = Column(Integer, primary_key=True, index=True)
    distributor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invited_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    invite_code = Column(String(32), default="", index=True)
    status = Column(String(30), default="bound", index=True)
    source = Column(String(30), default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommissionLedger(Base):
    """佣金流水（P0 兼容旧表）"""
    __tablename__ = "commission_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    distributor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invited_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_registration_id = Column(Integer, ForeignKey("event_registrations.id"), nullable=True, index=True)
    source_type = Column(String(30), default="order")
    status = Column(String(30), default="pending", index=True)
    amount = Column(DECIMAL(10, 2), default=0)
    rate = Column(DECIMAL(5, 2), default=0)
    note = Column(Text, default="")
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WithdrawalRequest(Base):
    """提现申请（P0 兼容旧表）"""
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    distributor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0)
    account_name = Column(String(100), default="")
    account_type = Column(String(30), default="wechat")
    account_no = Column(String(100), default="")
    status = Column(String(30), default="pending", index=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    reject_reason = Column(Text, default="")
    paid_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
