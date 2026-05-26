"""
权限管理与分销系统管理接口
包含：
- P0 兼容接口
- 正式版只读查询接口
- 当前阶段新增：用户侧绑定接口、分润规则管理接口、代理申请接口
- 当前阶段新增：正式提现流、分润规则停用、绑定状态流转
"""
from datetime import datetime, timezone, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, cast, String, func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user, hash_password
from app.models.admin import AdminUser
from app.models.user import User
from app.models.event import Event, EventRegistration
from app.models.permission_distribution import (
    AdminRolePermission,
    DistributorProfile,
    CommissionLedger,
    WithdrawalRequest,
    Role,
    Permission,
    RolePermission,
    UserRoleBinding,
    DataScope,
    OrganizerProfile,
    AgentProfile,
    ReferralBinding,
    RevenueShareRule,
    AgentCommissionLedger,
    AgentTeamManagementBonusLedger,
    UserReferralRewardLedger,
    AgentWalletAccount,
    AgentWithdrawalRequest,
    AuditLog,
    IdempotencyRecord,
)
from app.schemas.permission_distribution import (
    PermissionItem,
    AdminPermissionMeResponse,
    AdminAccountItem,
    AdminAccountListResponse,
    AdminAccountCreateRequest,
    AdminAccountToggleRequest,
    DistributorListItem,
    DistributorListResponse,
    CommissionLedgerItem,
    CommissionLedgerListResponse,
    WithdrawalRequestItem,
    WithdrawalRequestListResponse,
    WithdrawalReviewRequest,
    RoleListItem,
    RoleListResponse,
    PermissionListItem,
    PermissionListResponse,
    UserRoleBindingItem,
    UserRoleBindingListResponse,
    DataScopeItem,
    DataScopeListResponse,
    OrganizerProfileItem,
    OrganizerProfileListResponse,
    AgentProfileItem,
    AgentProfileListResponse,
    ReferralBindingItem,
    ReferralBindingListResponse,
    RevenueShareRuleItem,
    RevenueShareRuleListResponse,
    AgentCommissionLedgerItem,
    AgentCommissionLedgerListResponse,
    AgentTeamManagementBonusLedgerItem,
    AgentTeamManagementBonusLedgerListResponse,
    UserReferralRewardLedgerItem,
    UserReferralRewardLedgerListResponse,
    AgentWalletAccountItem,
    AgentWalletAccountListResponse,
    AgentWithdrawalRequestItem,
    AgentWithdrawalRequestListResponse,
    AuditLogItem,
    AuditLogListResponse,
    IdempotencyRecordItem,
    IdempotencyRecordListResponse,
    ReferralBindingCreateRequest,
    RevenueShareRuleCreateRequest,
    RevenueShareRuleUpdateRequest,
    ReferralBindingStatusUpdateRequest,
    AgentWithdrawalCreateRequest,
    AgentWithdrawalReviewRequest,
)

router = APIRouter(prefix="/api/admin", tags=["权限管理与分销系统"])
user_router = APIRouter(prefix="/api/distribution", tags=["分销用户接口"])

DEFAULT_ROLE_PERMISSIONS = {
    "super_admin": [
        ("dashboard.view", "查看仪表盘"),
        ("admin_users.manage", "管理后台账号"),
        ("events.review", "审核活动"),
        ("certs.review", "审核主办方"),
        ("ui_config.manage", "管理UI装修"),
        ("distribution.view", "查看分销数据"),
        ("distribution.review_withdrawal", "审核提现"),
        ("rbac.view", "查看正式权限模型"),
        ("audit.view", "查看审计日志"),
    ],
    "operator": [
        ("dashboard.view", "查看仪表盘"),
        ("events.review", "审核活动"),
        ("certs.review", "审核主办方"),
        ("distribution.view", "查看分销数据"),
        ("rbac.view", "查看正式权限模型"),
    ],
    "finance": [
        ("dashboard.view", "查看仪表盘"),
        ("distribution.view", "查看分销数据"),
        ("distribution.review_withdrawal", "审核提现"),
        ("audit.view", "查看审计日志"),
    ],
}

FORMAL_ROLES = [
    {"code": "super_admin", "name": "超级管理员", "status": "active"},
    {"code": "finance_admin", "name": "财务管理员", "status": "active"},
    {"code": "operator", "name": "运营管理员", "status": "active"},
    {"code": "organizer", "name": "主理人", "status": "active"},
    {"code": "agent", "name": "共享合伙人", "status": "active"},
    {"code": "user", "name": "普通用户", "status": "active"},
]

FORMAL_PERMISSIONS = [
    {"code": "admin_users.manage", "name": "管理后台账号", "module": "admin_users", "action": "manage"},
    {"code": "distribution.view", "name": "查看分销数据", "module": "distribution", "action": "view"},
    {"code": "distribution.withdraw.review", "name": "审核提现", "module": "distribution", "action": "review"},
    {"code": "agent.apply.review", "name": "审核共享合伙人", "module": "agent", "action": "review"},
    {"code": "reward.reverse", "name": "冲正奖励", "module": "reward", "action": "reverse"},
    {"code": "audit.view", "name": "查看审计日志", "module": "audit", "action": "view"},
    {"code": "organizer.manage", "name": "管理主理人", "module": "organizer", "action": "manage"},
    {"code": "rbac.view", "name": "查看正式权限模型", "module": "rbac", "action": "view"},
]

FORMAL_ROLE_PERMISSION_MAP = {
    "super_admin": [
        "admin_users.manage",
        "distribution.view",
        "distribution.withdraw.review",
        "agent.apply.review",
        "reward.reverse",
        "audit.view",
        "organizer.manage",
        "rbac.view",
    ],
    "finance_admin": [
        "distribution.view",
        "distribution.withdraw.review",
        "audit.view",
        "rbac.view",
    ],
    "operator": [
        "distribution.view",
        "organizer.manage",
        "agent.apply.review",
        "rbac.view",
    ],
    "organizer": [],
    "agent": [],
    "user": [],
}

FORMAL_DATA_SCOPES = [
    {"role_code": "finance_admin", "scope_code": "all", "resource_type": "withdrawal", "config_json": {}},
    {"role_code": "finance_admin", "scope_code": "all", "resource_type": "commission", "config_json": {}},
    {"role_code": "operator", "scope_code": "assigned", "resource_type": "withdrawal", "config_json": {}},
    {"role_code": "operator", "scope_code": "assigned", "resource_type": "reward", "config_json": {}},
    {"role_code": "organizer", "scope_code": "self", "resource_type": "organizer", "config_json": {}},
    {"role_code": "agent", "scope_code": "self", "resource_type": "commission", "config_json": {}},
    {"role_code": "agent", "scope_code": "self", "resource_type": "withdrawal", "config_json": {}},
]


def _iso(dt):
    return dt.isoformat() if dt else None


def _json_dump(value):
    return json.dumps(value or {}, ensure_ascii=False)


def _json_load(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _parse_dt(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_referral_binding_item(row: ReferralBinding, user_map: dict[int, User]) -> ReferralBindingItem:
    invited_user = user_map.get(row.invited_user_id)
    inviter_user = user_map.get(row.inviter_user_id)
    return ReferralBindingItem(
        id=row.id,
        invited_user_id=row.invited_user_id,
        invited_user_name=(invited_user.nickname if invited_user else ""),
        inviter_user_id=row.inviter_user_id,
        inviter_user_name=(inviter_user.nickname if inviter_user else ""),
        inviter_type=row.inviter_type or "",
        binding_type=row.binding_type or "",
        source_channel=row.source_channel or "",
        source_code=row.source_code or "",
        source_scene=getattr(row, "source_scene", "") or "",
        source_platform=getattr(row, "source_platform", "mini_program") or "mini_program",
        campaign_code=row.campaign_code or "",
        landing_page=row.landing_page or "",
        status=row.status or "",
        attribution_status=getattr(row, "attribution_status", "active") or "active",
        lock_days=getattr(row, "lock_days", 180) or 180,
        locked_until=_iso(getattr(row, "locked_until", None)),
        first_order_registration_id=row.first_order_registration_id,
        invalid_reason=row.invalid_reason or "",
        idempotency_key=row.idempotency_key or "",
        bound_at=_iso(row.bound_at),
        locked_at=_iso(row.locked_at),
        invalidated_at=_iso(row.invalidated_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _build_agent_profile_item(row: AgentProfile, user: User | None, parent_user: User | None = None) -> AgentProfileItem:
    return AgentProfileItem(
        id=row.id,
        user_id=row.user_id,
        nickname=(user.nickname if user else ""),
        phone=(user.phone if user else ""),
        agent_code=row.agent_code or "",
        level=row.level or "level_1",
        agent_type=getattr(row, "agent_type", "promoter") or "promoter",
        parent_agent_user_id=getattr(row, "parent_agent_user_id", None),
        parent_agent_name=(parent_user.nickname if parent_user else ""),
        service_region=getattr(row, "service_region", "") or "",
        direct_commission_rate=float(getattr(row, "direct_commission_rate", 50) or 50),
        management_base_rate=float(getattr(row, "management_base_rate", 10) or 10),
        management_bonus_rate=float(getattr(row, "management_bonus_rate", 0) or 0),
        risk_level=getattr(row, "risk_level", "normal") or "normal",
        compliance_status=getattr(row, "compliance_status", "normal") or "normal",
        status=row.status or "pending",
        identity_label=row.identity_label or ("区域合伙人" if getattr(row, "agent_type", "") == "regional_partner" else "推广员"),
        bind_channel=row.bind_channel or "",
        approved_by=row.approved_by,
        approved_at=_iso(row.approved_at),
        reject_reason=row.reject_reason or "",
        note=row.note or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _build_revenue_share_rule_item(row: RevenueShareRule) -> RevenueShareRuleItem:
    return RevenueShareRuleItem(
        id=row.id,
        target_type=row.target_type,
        target_id=row.target_id,
        target_name_snapshot=row.target_name_snapshot or "",
        agent_level=row.agent_level or "level_1",
        commission_mode=row.commission_mode or "fixed_rate",
        commission_rate=float(row.commission_rate) if row.commission_rate is not None else None,
        commission_amount=float(row.commission_amount) if row.commission_amount is not None else None,
        effective_status=row.effective_status or "active",
        effective_from=_iso(row.effective_from),
        effective_to=_iso(row.effective_to),
        created_by=row.created_by,
        updated_by=row.updated_by,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _build_agent_withdrawal_item(row: AgentWithdrawalRequest, user_map: dict[int, User], admin_map: dict[int, AdminUser]) -> AgentWithdrawalRequestItem:
    user = user_map.get(row.agent_user_id)
    reviewed_admin = admin_map.get(row.reviewed_by) if row.reviewed_by else None
    return AgentWithdrawalRequestItem(
        id=row.id,
        agent_user_id=row.agent_user_id,
        agent_name=(user.nickname if user else ""),
        amount=float(row.amount) if row.amount else 0,
        account_name=row.account_name or "",
        account_type=row.account_type or "wechat",
        account_no=row.account_no or "",
        status=row.status or "pending",
        reviewed_by=row.reviewed_by,
        reviewed_admin_name=(reviewed_admin.display_name if reviewed_admin else ""),
        reviewed_at=_iso(row.reviewed_at),
        paid_at=_iso(row.paid_at),
        reject_reason=row.reject_reason or "",
        idempotency_key=row.idempotency_key or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _write_audit_log(db: Session, actor_type: str, actor_id: int | None, action_code: str, biz_type: str, target_type: str, target_id: str, after_json: dict, remark: str = "", idempotency_key: str = ""):
    db.add(AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action_code=action_code,
        biz_type=biz_type,
        target_type=target_type,
        target_id=target_id,
        after_json=_json_dump(after_json),
        idempotency_key=idempotency_key,
        remark=remark,
    ))


def ensure_default_role_permissions(db: Session):
    existing_count = db.query(AdminRolePermission).count()
    if existing_count == 0:
        for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            for key, name in permissions:
                db.add(AdminRolePermission(role=role, permission_key=key, permission_name=name))

    if db.query(Role).count() == 0:
        for item in FORMAL_ROLES:
            db.add(Role(**item))

    if db.query(Permission).count() == 0:
        for item in FORMAL_PERMISSIONS:
            db.add(Permission(**item))

    if db.query(RolePermission).count() == 0:
        for role_code, permission_codes in FORMAL_ROLE_PERMISSION_MAP.items():
            for permission_code in permission_codes:
                db.add(RolePermission(role_code=role_code, permission_code=permission_code))

    if db.query(DataScope).count() == 0:
        for item in FORMAL_DATA_SCOPES:
            db.add(
                DataScope(
                    role_code=item["role_code"],
                    scope_code=item["scope_code"],
                    resource_type=item["resource_type"],
                    config_json=_json_dump(item["config_json"]),
                )
            )

    db.commit()


def _format_dt(value):
    if not value:
        return ""
    try:
        return value.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return _iso(value) or ""


def _commission_status_display(status: str | None):
    mapping = {
        "pending": ("待结算", "pending"),
        "settled": ("可提现", "ready"),
        "available": ("可提现", "ready"),
        "paid": ("已到账", "success"),
        "reversed": ("已冲正", "disabled"),
        "cancelled": ("已取消", "disabled"),
    }
    return mapping.get(status or "", (status or "待结算", "pending"))


def _withdrawal_status_display(status: str | None):
    mapping = {
        "pending": ("审核中", "review"),
        "approved": ("已通过", "review"),
        "paid": ("已打款", "success"),
        "rejected": ("已驳回", "failed"),
        "cancelled": ("已取消", "failed"),
    }
    return mapping.get(status or "", (status or "审核中", "review"))


def _build_distribution_rules():
    return [
        "好友首次报名平台官方活动，按规则生成待结算返佣。",
        "活动完成或订单确认后，返佣转入可提现余额。",
        "提现申请提交后，平台将在 1-3 个工作日内审核处理。",
    ]


def _build_distribution_timeline():
    return [
        {"id": "dt1", "title": "分享专属邀请码", "desc": "转发给好友或社群，好友通过你的邀请码完成绑定", "chip": "第一步"},
        {"id": "dt2", "title": "好友完成报名支付", "desc": "系统记录订单来源，进入待结算返佣", "chip": "第二步"},
        {"id": "dt3", "title": "审核结算后提现", "desc": "订单确认后转入可提现余额，可发起提现", "chip": "第三步"},
    ]


def _default_distribution_profile(current_user: User):
    return {
        "isDistributor": False,
        "levelName": "待开通",
        "inviterCode": f"YF{current_user.id:06d}",
        "shareTitle": "邀好友上屿风，一起参加活动还能赚奖励",
        "shareSubtitle": "开通共享合伙人后，可获得专属邀请码与返佣权益。",
        "stats": {
            "totalIncome": 0,
            "withdrawableAmount": 0,
            "pendingAmount": 0,
            "invitedFriends": 0,
            "paidOrders": 0,
            "conversionRate": 0,
        },
        "rules": _build_distribution_rules(),
        "timeline": _build_distribution_timeline(),
        "inviteHighlights": [],
        "recentCommissions": [],
        "recentWithdrawals": [],
        "recentOrders": [],
    }


def _build_commission_api_item(ledger, invited_user=None, event=None, registration=None):
    status, status_class = _commission_status_display(getattr(ledger, "status", "pending"))
    amount = float(getattr(ledger, "amount", 0) or 0)
    order_amount = float(getattr(registration, "total_price", 0) or 0) if registration else 0
    order_title = getattr(event, "title", "") if event else "屿风订单"
    source_type = getattr(ledger, "source_type", "order") or "order"
    type_text = "活动报名返佣" if source_type == "order" else "邀请奖励"
    return {
        "id": getattr(ledger, "id", None),
        "friendName": (getattr(invited_user, "nickname", "") or "屿风用户"),
        "type": type_text,
        "amount": amount,
        "orderAmount": order_amount,
        "orderTitle": order_title,
        "date": _format_dt(getattr(ledger, "created_at", None)),
        "status": status,
        "statusClass": status_class,
        "note": getattr(ledger, "note", "") or "返佣记录已生成，按平台规则结算。",
    }


def _build_withdrawal_api_item(row):
    status, status_class = _withdrawal_status_display(getattr(row, "status", "pending"))
    account_type = getattr(row, "account_type", "wechat") or "wechat"
    account_label = "微信零钱" if account_type == "wechat" else account_type
    return {
        "id": getattr(row, "id", None),
        "amount": float(getattr(row, "amount", 0) or 0),
        "account": account_label,
        "requestedAt": _format_dt(getattr(row, "created_at", None)),
        "status": status,
        "statusClass": status_class,
        "note": getattr(row, "reject_reason", "") or ("到账成功，可在零钱明细查看。" if status_class == "success" else "平台将在 1-3 个工作日内处理。"),
    }


def _build_order_api_item(ledger, invited_user=None, event=None, registration=None):
    status, status_class = _commission_status_display(getattr(ledger, "status", "pending"))
    return {
        "id": f"order_{getattr(ledger, 'id', '')}",
        "friendName": (getattr(invited_user, "nickname", "") or "屿风用户"),
        "title": getattr(event, "title", "屿风活动报名") if event else "屿风活动报名",
        "amount": float(getattr(registration, "total_price", 0) or 0) if registration else 0,
        "reward": float(getattr(ledger, "amount", 0) or 0),
        "status": status,
        "statusClass": status_class,
        "date": _format_dt(getattr(ledger, "created_at", None)),
    }


@user_router.get("/profile")
def get_distribution_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(DistributorProfile).filter(DistributorProfile.user_id == current_user.id).first()
    if not profile:
        agent_profile = db.query(AgentProfile).filter(AgentProfile.user_id == current_user.id).first()
        wallet = db.query(AgentWalletAccount).filter(AgentWalletAccount.user_id == current_user.id).first()
        data = _default_distribution_profile(current_user)
        if agent_profile:
            data.update({
                "isDistributor": agent_profile.status == "approved",
                "levelName": agent_profile.identity_label or "共享合伙人",
                "inviterCode": agent_profile.agent_code or f"AG{current_user.id:06d}",
                "shareSubtitle": "好友通过你的专属邀请码报名后，按平台规则获得返佣。" if agent_profile.status == "approved" else "申请已提交，审核通过后将开启分销权益。",
            })
            if wallet:
                data["stats"].update({
                    "totalIncome": float(wallet.total_earned or 0),
                    "withdrawableAmount": float(wallet.withdrawable_balance or 0),
                    "pendingAmount": float(wallet.frozen_balance or 0),
                })
        return data

    invited_count = db.query(sa_func.count(ReferralBinding.id)).filter(ReferralBinding.inviter_user_id == current_user.id).scalar() or profile.total_invited_users or 0
    paid_orders = profile.total_paid_orders or db.query(sa_func.count(CommissionLedger.id)).filter(CommissionLedger.distributor_user_id == current_user.id).scalar() or 0
    pending_amount = db.query(sa_func.coalesce(sa_func.sum(CommissionLedger.amount), 0)).filter(
        CommissionLedger.distributor_user_id == current_user.id,
        CommissionLedger.status == "pending",
    ).scalar() or 0
    conversion_rate = round((float(paid_orders) / float(invited_count) * 100), 1) if invited_count else 0
    recent_commissions = list_distribution_commissions(1, 3, current_user, db).get("list", [])
    recent_withdrawals = list_distribution_withdrawals(1, 3, current_user, db).get("list", [])
    recent_orders = list_distribution_orders(1, 3, current_user, db).get("list", [])
    return {
        "isDistributor": (profile.status or "pending") == "approved",
        "levelName": profile.display_name or ("星推官" if profile.status == "approved" else "待审核"),
        "inviterCode": profile.invite_code or f"YF{current_user.id:06d}",
        "shareTitle": "邀好友上屿风，一起参加活动还能赚奖励",
        "shareSubtitle": "好友通过你的专属邀请码报名后，按平台规则获得返佣。",
        "stats": {
            "totalIncome": float(profile.total_commission_earned or 0),
            "withdrawableAmount": float(profile.withdrawable_balance or 0),
            "pendingAmount": float(pending_amount or 0),
            "invitedFriends": int(invited_count or 0),
            "paidOrders": int(paid_orders or 0),
            "conversionRate": conversion_rate,
        },
        "rules": _build_distribution_rules(),
        "timeline": _build_distribution_timeline(),
        "inviteHighlights": [],
        "recentCommissions": recent_commissions,
        "recentWithdrawals": recent_withdrawals,
        "recentOrders": recent_orders,
    }


@user_router.get("/commissions")
def list_distribution_commissions(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CommissionLedger).filter(CommissionLedger.distributor_user_id == current_user.id)
    total = query.count()
    rows = query.order_by(CommissionLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    invited_ids = [r.invited_user_id for r in rows if r.invited_user_id]
    reg_ids = [r.event_registration_id for r in rows if r.event_registration_id]
    invited_map = {u.id: u for u in db.query(User).filter(User.id.in_(invited_ids)).all()} if invited_ids else {}
    reg_map = {r.id: r for r in db.query(EventRegistration).filter(EventRegistration.id.in_(reg_ids)).all()} if reg_ids else {}
    event_ids = [r.event_id for r in reg_map.values() if r.event_id]
    event_map = {e.id: e for e in db.query(Event).filter(Event.id.in_(event_ids)).all()} if event_ids else {}
    items = []
    for row in rows:
        registration = reg_map.get(row.event_registration_id)
        event = event_map.get(registration.event_id) if registration else None
        items.append(_build_commission_api_item(row, invited_map.get(row.invited_user_id), event, registration))
    return {"list": items, "items": items, "total": total, "page": page, "page_size": page_size}


@user_router.get("/withdrawals")
def list_distribution_withdrawals(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    legacy_rows = db.query(WithdrawalRequest).filter(WithdrawalRequest.distributor_user_id == current_user.id).order_by(WithdrawalRequest.created_at.desc()).all()
    agent_rows = db.query(AgentWithdrawalRequest).filter(AgentWithdrawalRequest.agent_user_id == current_user.id).order_by(AgentWithdrawalRequest.created_at.desc()).all()
    all_rows = sorted(legacy_rows + agent_rows, key=lambda r: r.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    total = len(all_rows)
    start = (page - 1) * page_size
    items = [_build_withdrawal_api_item(row) for row in all_rows[start:start + page_size]]
    return {"list": items, "items": items, "total": total, "page": page, "page_size": page_size}


@user_router.get("/orders")
def list_distribution_orders(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CommissionLedger).filter(CommissionLedger.distributor_user_id == current_user.id)
    total = query.count()
    rows = query.order_by(CommissionLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    invited_ids = [r.invited_user_id for r in rows if r.invited_user_id]
    reg_ids = [r.event_registration_id for r in rows if r.event_registration_id]
    invited_map = {u.id: u for u in db.query(User).filter(User.id.in_(invited_ids)).all()} if invited_ids else {}
    reg_map = {r.id: r for r in db.query(EventRegistration).filter(EventRegistration.id.in_(reg_ids)).all()} if reg_ids else {}
    event_ids = [r.event_id for r in reg_map.values() if r.event_id]
    event_map = {e.id: e for e in db.query(Event).filter(Event.id.in_(event_ids)).all()} if event_ids else {}
    items = []
    for row in rows:
        registration = reg_map.get(row.event_registration_id)
        event = event_map.get(registration.event_id) if registration else None
        items.append(_build_order_api_item(row, invited_map.get(row.invited_user_id), event, registration))
    return {"list": items, "items": items, "total": total, "page": page, "page_size": page_size}


@user_router.post("/bindings", response_model=ReferralBindingItem)
def create_referral_binding(
    req: ReferralBindingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.inviter_user_id == current_user.id:
        raise HTTPException(400, "不能绑定自己为推荐人")

    inviter = db.query(User).filter(User.id == req.inviter_user_id).first()
    if not inviter:
        raise HTTPException(404, "推荐人不存在")

    if req.inviter_type == "agent":
        agent_profile = db.query(AgentProfile).filter(AgentProfile.user_id == req.inviter_user_id, AgentProfile.status == "approved").first()
        if not agent_profile:
            raise HTTPException(400, "推荐人不是已审核通过的共享合伙人")
        if req.binding_type != "agent_referral":
            raise HTTPException(400, "共享合伙人只能创建 agent_referral 绑定")
    else:
        if req.binding_type != "first_order_reward":
            raise HTTPException(400, "普通用户只能创建 first_order_reward 绑定")

    existing_idempotency = db.query(IdempotencyRecord).filter(IdempotencyRecord.idempotency_key == req.idempotency_key).first()
    if existing_idempotency and existing_idempotency.status == "success":
        existing_binding = db.query(ReferralBinding).filter(ReferralBinding.idempotency_key == req.idempotency_key).first()
        if existing_binding:
            user_map = {u.id: u for u in db.query(User).filter(User.id.in_([existing_binding.invited_user_id, existing_binding.inviter_user_id])).all()}
            return _build_referral_binding_item(existing_binding, user_map)

    existing_binding = db.query(ReferralBinding).filter(ReferralBinding.invited_user_id == current_user.id).first()
    if existing_binding:
        raise HTTPException(400, "该用户已存在有效邀请绑定，不允许重复绑定")

    idem = existing_idempotency
    if not idem:
        idem = IdempotencyRecord(
            biz_type="referral_binding",
            biz_key=f"invited_user:{current_user.id}",
            idempotency_key=req.idempotency_key,
            request_hash=_json_dump(req.model_dump()),
            status="processing",
        )
        db.add(idem)
        db.flush()

    row = ReferralBinding(
        invited_user_id=current_user.id,
        inviter_user_id=req.inviter_user_id,
        inviter_type=req.inviter_type,
        binding_type=req.binding_type,
        source_channel=req.source_channel,
        source_code=req.source_code,
        source_scene=req.source_scene,
        source_platform=req.source_platform,
        landing_page=req.landing_page,
        campaign_code=req.campaign_code,
        binding_context_json=_json_dump(req.binding_context_json),
        status="bound",
        attribution_status="active",
        lock_days=180,
        bound_at=datetime.now(timezone.utc),
        locked_at=datetime.now(timezone.utc),
        locked_until=datetime.now(timezone.utc) + timedelta(days=180),
        idempotency_key=req.idempotency_key,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "绑定已存在，不能重复创建")

    idem.status = "success"
    idem.response_snapshot = _json_dump({"binding_id": row.id})
    _write_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action_code="referral.binding.create",
        biz_type="referral_binding",
        target_type="referral_binding",
        target_id=str(row.id),
        after_json={
            "invited_user_id": row.invited_user_id,
            "inviter_user_id": row.inviter_user_id,
            "binding_type": row.binding_type,
            "source_channel": row.source_channel,
            "source_scene": row.source_scene,
            "source_platform": row.source_platform,
            "lock_days": row.lock_days,
            "locked_until": _iso(row.locked_until),
        },
        idempotency_key=req.idempotency_key,
    )
    db.commit()
    db.refresh(row)
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_([row.invited_user_id, row.inviter_user_id])).all()}
    return _build_referral_binding_item(row, user_map)


@user_router.post("/agent/apply", response_model=AgentProfileItem)
def apply_agent_profile(
    agent_type: str = "promoter",
    parent_agent_user_id: int | None = None,
    service_region: str = "",
    bind_channel: str = "mini_program",
    note: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(AgentProfile).filter(AgentProfile.user_id == current_user.id).first()
    if existing:
        return _build_agent_profile_item(existing, current_user)

    row = AgentProfile(
        user_id=current_user.id,
        agent_code=f"AG{current_user.id:06d}",
        level="level_1",
        agent_type=agent_type if agent_type in ("regional_partner", "promoter") else "promoter",
        parent_agent_user_id=parent_agent_user_id,
        service_region=service_region,
        direct_commission_rate=70 if agent_type == "regional_partner" else 50,
        management_base_rate=10 if agent_type == "regional_partner" else 0,
        management_bonus_rate=0,
        status="pending",
        bind_channel=bind_channel,
        identity_label="区域合伙人" if agent_type == "regional_partner" else "推广员",
        note=note,
    )
    db.add(row)
    db.flush()
    _write_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action_code="agent.apply",
        biz_type="agent_profile",
        target_type="agent_profile",
        target_id=str(row.id),
        after_json={"user_id": row.user_id, "agent_code": row.agent_code, "status": row.status},
        remark="用户发起共享合伙人申请",
    )
    db.commit()
    db.refresh(row)
    return _build_agent_profile_item(row, current_user)


@user_router.post("/withdrawals", response_model=AgentWithdrawalRequestItem)
def create_agent_withdrawal(
    req: AgentWithdrawalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent_profile = db.query(AgentProfile).filter(AgentProfile.user_id == current_user.id, AgentProfile.status == "approved").first()
    if not agent_profile:
        raise HTTPException(400, "当前用户不是已审核通过的共享合伙人")

    wallet = db.query(AgentWalletAccount).filter(AgentWalletAccount.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(400, "代理钱包不存在")
    if float(wallet.withdrawable_balance or 0) < req.amount:
        raise HTTPException(400, "可提现余额不足")

    idem = db.query(IdempotencyRecord).filter(IdempotencyRecord.idempotency_key == req.idempotency_key).first()
    if idem and idem.status == "success":
        existing = db.query(AgentWithdrawalRequest).filter(AgentWithdrawalRequest.idempotency_key == req.idempotency_key).first()
        if existing:
            return _build_agent_withdrawal_item(existing, {current_user.id: current_user}, {})

    if not idem:
        idem = IdempotencyRecord(
            biz_type="agent_withdrawal",
            biz_key=f"agent_user:{current_user.id}",
            idempotency_key=req.idempotency_key,
            request_hash=_json_dump(req.model_dump()),
            status="processing",
        )
        db.add(idem)
        db.flush()

    wallet.withdrawable_balance = float(wallet.withdrawable_balance or 0) - req.amount
    wallet.frozen_balance = float(wallet.frozen_balance or 0) + req.amount

    row = AgentWithdrawalRequest(
        agent_user_id=current_user.id,
        amount=req.amount,
        account_name=req.account_name,
        account_type=req.account_type,
        account_no=req.account_no,
        status="pending",
        idempotency_key=req.idempotency_key,
    )
    db.add(row)
    db.flush()
    idem.status = "success"
    idem.response_snapshot = _json_dump({"withdrawal_id": row.id})
    _write_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action_code="agent.withdrawal.create",
        biz_type="agent_withdrawal",
        target_type="agent_withdrawal",
        target_id=str(row.id),
        after_json={"amount": req.amount, "account_type": req.account_type},
        idempotency_key=req.idempotency_key,
    )
    db.commit()
    db.refresh(row)
    return _build_agent_withdrawal_item(row, {current_user.id: current_user}, {})


@router.post("/formal/revenue-share-rules", response_model=RevenueShareRuleItem)
def create_revenue_share_rule(
    req: RevenueShareRuleCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if req.commission_mode == "fixed_rate" and req.commission_rate is None:
        raise HTTPException(400, "fixed_rate 模式必须提供 commission_rate")
    if req.commission_mode == "fixed_amount" and req.commission_amount is None:
        raise HTTPException(400, "fixed_amount 模式必须提供 commission_amount")

    existing = db.query(RevenueShareRule).filter(
        RevenueShareRule.target_type == req.target_type,
        RevenueShareRule.target_id == req.target_id,
        RevenueShareRule.agent_level == req.agent_level,
        RevenueShareRule.effective_status == "active",
    ).first()
    if existing and req.effective_status == "active":
        raise HTTPException(400, "同一目标当前已存在生效中的分润规则")

    row = RevenueShareRule(
        target_type=req.target_type,
        target_id=req.target_id,
        target_name_snapshot=req.target_name_snapshot,
        agent_level=req.agent_level,
        commission_mode=req.commission_mode,
        commission_rate=req.commission_rate,
        commission_amount=req.commission_amount,
        effective_status=req.effective_status,
        effective_from=_parse_dt(req.effective_from),
        effective_to=_parse_dt(req.effective_to),
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(row)
    db.flush()
    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="revenue_share_rule.create",
        biz_type="revenue_share_rule",
        target_type="revenue_share_rule",
        target_id=str(row.id),
        after_json={
            "target_type": row.target_type,
            "target_id": row.target_id,
            "commission_mode": row.commission_mode,
            "commission_rate": float(row.commission_rate) if row.commission_rate is not None else None,
            "commission_amount": float(row.commission_amount) if row.commission_amount is not None else None,
            "effective_status": row.effective_status,
        },
    )
    db.commit()
    db.refresh(row)
    return _build_revenue_share_rule_item(row)


@router.post("/formal/revenue-share-rules/{rule_id}", response_model=RevenueShareRuleItem)
def update_revenue_share_rule(
    rule_id: int,
    req: RevenueShareRuleUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(RevenueShareRule).filter(RevenueShareRule.id == rule_id).first()
    if not row:
        raise HTTPException(404, "分润规则不存在")

    payload = req.model_dump(exclude_unset=True)
    if "target_name_snapshot" in payload:
        row.target_name_snapshot = payload["target_name_snapshot"]
    if "agent_level" in payload:
        row.agent_level = payload["agent_level"]
    if "commission_mode" in payload:
        row.commission_mode = payload["commission_mode"]
    if "commission_rate" in payload:
        row.commission_rate = payload["commission_rate"]
    if "commission_amount" in payload:
        row.commission_amount = payload["commission_amount"]
    if "effective_status" in payload:
        row.effective_status = payload["effective_status"]
    if "effective_from" in payload:
        row.effective_from = _parse_dt(payload["effective_from"])
    if "effective_to" in payload:
        row.effective_to = _parse_dt(payload["effective_to"])
    row.updated_by = admin.id

    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="revenue_share_rule.update",
        biz_type="revenue_share_rule",
        target_type="revenue_share_rule",
        target_id=str(row.id),
        after_json=payload,
    )
    db.commit()
    db.refresh(row)
    return _build_revenue_share_rule_item(row)


@router.post("/formal/revenue-share-rules/{rule_id}/disable", response_model=RevenueShareRuleItem)
def disable_revenue_share_rule(
    rule_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(RevenueShareRule).filter(RevenueShareRule.id == rule_id).first()
    if not row:
        raise HTTPException(404, "分润规则不存在")
    row.effective_status = "inactive"
    row.updated_by = admin.id
    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="revenue_share_rule.disable",
        biz_type="revenue_share_rule",
        target_type="revenue_share_rule",
        target_id=str(row.id),
        after_json={"effective_status": "inactive"},
    )
    db.commit()
    db.refresh(row)
    return _build_revenue_share_rule_item(row)


@router.post("/formal/agents/{agent_id}/review", response_model=AgentProfileItem)
def review_agent_profile(
    agent_id: int,
    action: str,
    reject_reason: str = "",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if action not in {"approve", "reject"}:
        raise HTTPException(400, "action 仅支持 approve/reject")

    row = db.query(AgentProfile).filter(AgentProfile.id == agent_id).first()
    if not row:
        raise HTTPException(404, "共享合伙人申请不存在")

    if action == "approve":
        row.status = "approved"
        row.reject_reason = ""
        row.approved_by = admin.id
        row.approved_at = datetime.now(timezone.utc)

        existing_binding = db.query(UserRoleBinding).filter(
            UserRoleBinding.principal_type == "user",
            UserRoleBinding.principal_id == row.user_id,
            UserRoleBinding.role_code == "agent",
        ).first()
        if not existing_binding:
            db.add(UserRoleBinding(
                principal_type="user",
                principal_id=row.user_id,
                role_code="agent",
                source="agent_apply",
                status="active",
                granted_by=admin.id,
                granted_at=datetime.now(timezone.utc),
            ))

        existing_wallet = db.query(AgentWalletAccount).filter(AgentWalletAccount.user_id == row.user_id).first()
        if not existing_wallet:
            db.add(AgentWalletAccount(user_id=row.user_id, account_type="agent_commission"))
    else:
        row.status = "rejected"
        row.reject_reason = reject_reason or "审核未通过"
        row.approved_by = admin.id
        row.approved_at = datetime.now(timezone.utc)

    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="agent.review",
        biz_type="agent_profile",
        target_type="agent_profile",
        target_id=str(row.id),
        after_json={"status": row.status, "reject_reason": row.reject_reason},
    )
    db.commit()
    db.refresh(row)
    user = db.query(User).filter(User.id == row.user_id).first()
    return _build_agent_profile_item(row, user)


@router.post("/formal/referral-bindings/{binding_id}/status", response_model=ReferralBindingItem)
def update_referral_binding_status(
    binding_id: int,
    req: ReferralBindingStatusUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(ReferralBinding).filter(ReferralBinding.id == binding_id).first()
    if not row:
        raise HTTPException(404, "邀请绑定不存在")

    if req.action == "lock":
        row.status = "locked"
        row.locked_at = datetime.now(timezone.utc)
    else:
        row.status = "invalid"
        row.invalidated_at = datetime.now(timezone.utc)
        row.invalid_reason = req.invalid_reason or "后台置为失效"

    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="referral_binding.status_update",
        biz_type="referral_binding",
        target_type="referral_binding",
        target_id=str(row.id),
        after_json={"action": req.action, "status": row.status, "invalid_reason": row.invalid_reason},
    )
    db.commit()
    db.refresh(row)
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_([row.invited_user_id, row.inviter_user_id])).all()}
    return _build_referral_binding_item(row, user_map)


@router.post("/formal/agent-withdrawals/{withdrawal_id}/review", response_model=AgentWithdrawalRequestItem)
def review_agent_withdrawal(
    withdrawal_id: int,
    req: AgentWithdrawalReviewRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(AgentWithdrawalRequest).filter(AgentWithdrawalRequest.id == withdrawal_id).first()
    if not row:
        raise HTTPException(404, "正式提现申请不存在")

    wallet = db.query(AgentWalletAccount).filter(AgentWalletAccount.user_id == row.agent_user_id).first()
    if not wallet:
        raise HTTPException(400, "代理钱包不存在")

    amount = float(row.amount or 0)
    if req.action == "approve":
        row.status = "approved"
        row.reject_reason = ""
        row.reviewed_by = admin.id
        row.reviewed_at = datetime.now(timezone.utc)
    elif req.action == "reject":
        row.status = "rejected"
        row.reject_reason = req.reject_reason or "审核未通过"
        row.reviewed_by = admin.id
        row.reviewed_at = datetime.now(timezone.utc)
        wallet.frozen_balance = max(float(wallet.frozen_balance or 0) - amount, 0)
        wallet.withdrawable_balance = float(wallet.withdrawable_balance or 0) + amount
    else:
        row.status = "paid"
        row.reject_reason = ""
        row.reviewed_by = admin.id
        row.reviewed_at = datetime.now(timezone.utc)
        row.paid_at = datetime.now(timezone.utc)
        wallet.frozen_balance = max(float(wallet.frozen_balance or 0) - amount, 0)
        wallet.total_withdrawn = float(wallet.total_withdrawn or 0) + amount

    _write_audit_log(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action_code="agent.withdrawal.review",
        biz_type="agent_withdrawal",
        target_type="agent_withdrawal",
        target_id=str(row.id),
        after_json={"action": req.action, "status": row.status, "reject_reason": row.reject_reason},
    )
    db.commit()
    db.refresh(row)
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_([row.agent_user_id])).all()}
    admin_map = {admin.id: admin}
    return _build_agent_withdrawal_item(row, user_map, admin_map)


@router.get("/permissions/me", response_model=AdminPermissionMeResponse)
def get_my_permissions(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_default_role_permissions(db)
    rows = (
        db.query(AdminRolePermission)
        .filter(AdminRolePermission.role == (admin.role or "operator"))
        .order_by(AdminRolePermission.permission_key.asc())
        .all()
    )
    permissions = [PermissionItem(key=row.permission_key, name=row.permission_name or row.permission_key) for row in rows]
    return AdminPermissionMeResponse(role=admin.role or "operator", permissions=permissions)


@router.get("/formal/agent-withdrawals", response_model=AgentWithdrawalRequestListResponse)
def list_agent_withdrawals(
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AgentWithdrawalRequest)
    if status_filter != "all":
        query = query.filter(AgentWithdrawalRequest.status == status_filter)
    total = query.count()
    rows = query.order_by(AgentWithdrawalRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    agent_ids = [row.agent_user_id for row in rows]
    reviewed_admin_ids = [row.reviewed_by for row in rows if row.reviewed_by]
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(agent_ids)).all()} if agent_ids else {}
    admin_map = {a.id: a for a in db.query(AdminUser).filter(AdminUser.id.in_(reviewed_admin_ids)).all()} if reviewed_admin_ids else {}
    items = [_build_agent_withdrawal_item(row, user_map, admin_map) for row in rows]
    return AgentWithdrawalRequestListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/admin-users", response_model=AdminAccountListResponse)
def list_admin_users(
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AdminUser)
    if keyword:
        query = query.filter(or_(
            AdminUser.username.ilike(f"%{keyword}%"),
            AdminUser.display_name.ilike(f"%{keyword}%"),
            AdminUser.role.ilike(f"%{keyword}%"),
            cast(AdminUser.id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(AdminUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [AdminAccountItem(
        id=row.id,
        username=row.username,
        display_name=row.display_name or "",
        role=row.role or "operator",
        is_active=bool(row.is_active),
        last_login_at=_iso(row.last_login_at),
        created_at=_iso(row.created_at),
    ) for row in rows]
    return AdminAccountListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/admin-users", response_model=AdminAccountItem)
def create_admin_user(
    req: AdminAccountCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if existing:
        raise HTTPException(400, "后台账号已存在")
    row = AdminUser(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        role=req.role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AdminAccountItem(
        id=row.id,
        username=row.username,
        display_name=row.display_name or "",
        role=row.role or "operator",
        is_active=bool(row.is_active),
        last_login_at=_iso(row.last_login_at),
        created_at=_iso(row.created_at),
    )


@router.post("/admin-users/{admin_user_id}/toggle-active", response_model=AdminAccountItem)
def toggle_admin_user_active(
    admin_user_id: int,
    req: AdminAccountToggleRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(AdminUser).filter(AdminUser.id == admin_user_id).first()
    if not row:
        raise HTTPException(404, "后台账号不存在")
    if row.username == "admin" and not req.is_active:
        raise HTTPException(400, "默认超级管理员不可禁用")
    row.is_active = req.is_active
    db.commit()
    db.refresh(row)
    return AdminAccountItem(
        id=row.id,
        username=row.username,
        display_name=row.display_name or "",
        role=row.role or "operator",
        is_active=bool(row.is_active),
        last_login_at=_iso(row.last_login_at),
        created_at=_iso(row.created_at),
    )


@router.get("/distributors", response_model=DistributorListResponse)
def list_distributors(
    keyword: str = "",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(DistributorProfile, User).join(User, User.id == DistributorProfile.user_id)
    if status_filter != "all":
        query = query.filter(DistributorProfile.status == status_filter)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            User.phone.ilike(f"%{keyword}%"),
            DistributorProfile.invite_code.ilike(f"%{keyword}%"),
            DistributorProfile.display_name.ilike(f"%{keyword}%"),
            cast(DistributorProfile.user_id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(DistributorProfile.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [DistributorListItem(
        id=profile.id,
        user_id=profile.user_id,
        nickname=user.nickname or "",
        phone=user.phone or "",
        invite_code=profile.invite_code or "",
        display_name=profile.display_name or "",
        level=profile.level or "basic",
        status=profile.status or "pending",
        referrer_user_id=profile.referrer_user_id,
        total_invited_users=profile.total_invited_users or 0,
        total_paid_orders=profile.total_paid_orders or 0,
        total_commission_earned=float(profile.total_commission_earned) if profile.total_commission_earned else 0,
        withdrawable_balance=float(profile.withdrawable_balance) if profile.withdrawable_balance else 0,
        approved_at=_iso(profile.approved_at),
        created_at=_iso(profile.created_at),
    ) for profile, user in rows]
    return DistributorListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/commissions", response_model=CommissionLedgerListResponse)
def list_commissions(
    keyword: str = "",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CommissionLedger, User).join(User, User.id == CommissionLedger.distributor_user_id)
    if status_filter != "all":
        query = query.filter(CommissionLedger.status == status_filter)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            CommissionLedger.source_type.ilike(f"%{keyword}%"),
            CommissionLedger.note.ilike(f"%{keyword}%"),
            cast(CommissionLedger.id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(CommissionLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    invited_ids = list({row.invited_user_id for row, _ in rows if row.invited_user_id})
    invited_map = {u.id: u for u in db.query(User).filter(User.id.in_(invited_ids)).all()} if invited_ids else {}
    items = []
    for ledger, distributor in rows:
        invited_user = invited_map.get(ledger.invited_user_id) if ledger.invited_user_id else None
        items.append(CommissionLedgerItem(
            id=ledger.id,
            distributor_user_id=ledger.distributor_user_id,
            distributor_name=distributor.nickname or "",
            invited_user_id=ledger.invited_user_id,
            invited_user_name=(invited_user.nickname if invited_user else ""),
            event_registration_id=ledger.event_registration_id,
            source_type=ledger.source_type or "order",
            status=ledger.status or "pending",
            amount=float(ledger.amount) if ledger.amount else 0,
            rate=float(ledger.rate) if ledger.rate else 0,
            note=ledger.note or "",
            created_at=_iso(ledger.created_at),
            settled_at=_iso(ledger.settled_at),
        ))
    return CommissionLedgerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/withdrawals", response_model=WithdrawalRequestListResponse)
def list_withdrawals(
    keyword: str = "",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(WithdrawalRequest, User).join(User, User.id == WithdrawalRequest.distributor_user_id)
    if status_filter != "all":
        query = query.filter(WithdrawalRequest.status == status_filter)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            WithdrawalRequest.account_name.ilike(f"%{keyword}%"),
            WithdrawalRequest.account_no.ilike(f"%{keyword}%"),
            cast(WithdrawalRequest.id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(WithdrawalRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    admin_ids = list({row.reviewed_by_admin_id for row, _ in rows if row.reviewed_by_admin_id})
    admin_map = {a.id: a for a in db.query(AdminUser).filter(AdminUser.id.in_(admin_ids)).all()} if admin_ids else {}
    items = []
    for withdrawal, distributor in rows:
        reviewed_admin = admin_map.get(withdrawal.reviewed_by_admin_id) if withdrawal.reviewed_by_admin_id else None
        items.append(WithdrawalRequestItem(
            id=withdrawal.id,
            distributor_user_id=withdrawal.distributor_user_id,
            distributor_name=distributor.nickname or "",
            amount=float(withdrawal.amount) if withdrawal.amount else 0,
            account_name=withdrawal.account_name or "",
            account_type=withdrawal.account_type or "wechat",
            account_no=withdrawal.account_no or "",
            status=withdrawal.status or "pending",
            reject_reason=withdrawal.reject_reason or "",
            reviewed_by_admin_id=withdrawal.reviewed_by_admin_id,
            reviewed_admin_name=(reviewed_admin.display_name if reviewed_admin else ""),
            created_at=_iso(withdrawal.created_at),
            reviewed_at=_iso(withdrawal.reviewed_at),
            paid_at=_iso(withdrawal.paid_at),
        ))
    return WithdrawalRequestListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/withdrawals/{withdrawal_id}/review", response_model=WithdrawalRequestItem)
def review_withdrawal(
    withdrawal_id: int,
    req: WithdrawalReviewRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.query(WithdrawalRequest).filter(WithdrawalRequest.id == withdrawal_id).first()
    if not row:
        raise HTTPException(404, "提现申请不存在")
    if req.action == "approve":
        row.status = "approved"
        row.reject_reason = ""
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by_admin_id = admin.id
    elif req.action == "reject":
        row.status = "rejected"
        row.reject_reason = req.reject_reason or "审核未通过"
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by_admin_id = admin.id
    else:
        row.status = "paid"
        row.reject_reason = ""
        row.reviewed_at = datetime.now(timezone.utc)
        row.paid_at = datetime.now(timezone.utc)
        row.reviewed_by_admin_id = admin.id
    db.commit()
    db.refresh(row)
    distributor = db.query(User).filter(User.id == row.distributor_user_id).first()
    return WithdrawalRequestItem(
        id=row.id,
        distributor_user_id=row.distributor_user_id,
        distributor_name=(distributor.nickname if distributor else ""),
        amount=float(row.amount) if row.amount else 0,
        account_name=row.account_name or "",
        account_type=row.account_type or "wechat",
        account_no=row.account_no or "",
        status=row.status or "pending",
        reject_reason=row.reject_reason or "",
        reviewed_by_admin_id=row.reviewed_by_admin_id,
        reviewed_admin_name=admin.display_name or "",
        created_at=_iso(row.created_at),
        reviewed_at=_iso(row.reviewed_at),
        paid_at=_iso(row.paid_at),
    )


@router.get("/formal/roles", response_model=RoleListResponse)
def list_formal_roles(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_default_role_permissions(db)
    rows = db.query(Role).order_by(Role.id.asc()).all()
    items = [RoleListItem(id=row.id, code=row.code, name=row.name, status=row.status, created_at=_iso(row.created_at), updated_at=_iso(row.updated_at)) for row in rows]
    return RoleListResponse(items=items, total=len(items))


@router.get("/formal/permissions", response_model=PermissionListResponse)
def list_formal_permissions(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_default_role_permissions(db)
    rows = db.query(Permission).order_by(Permission.code.asc()).all()
    items = [PermissionListItem(id=row.id, code=row.code, name=row.name, module=row.module or "", action=row.action or "", created_at=_iso(row.created_at)) for row in rows]
    return PermissionListResponse(items=items, total=len(items))


@router.get("/formal/role-bindings", response_model=UserRoleBindingListResponse)
def list_role_bindings(
    principal_type: str = "all",
    role_code: str = "all",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(UserRoleBinding)
    if principal_type != "all":
        query = query.filter(UserRoleBinding.principal_type == principal_type)
    if role_code != "all":
        query = query.filter(UserRoleBinding.role_code == role_code)
    rows = query.order_by(UserRoleBinding.id.desc()).all()
    items = [UserRoleBindingItem(
        id=row.id,
        principal_type=row.principal_type,
        principal_id=row.principal_id,
        role_code=row.role_code,
        source=row.source or "",
        status=row.status or "",
        granted_by=row.granted_by,
        granted_at=_iso(row.granted_at),
        revoked_by=row.revoked_by,
        revoked_at=_iso(row.revoked_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    ) for row in rows]
    return UserRoleBindingListResponse(items=items, total=len(items))


@router.get("/formal/data-scopes", response_model=DataScopeListResponse)
def list_data_scopes(
    role_code: str = "all",
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_default_role_permissions(db)
    query = db.query(DataScope)
    if role_code != "all":
        query = query.filter(DataScope.role_code == role_code)
    rows = query.order_by(DataScope.id.asc()).all()
    items = [DataScopeItem(
        id=row.id,
        role_code=row.role_code,
        scope_code=row.scope_code,
        resource_type=row.resource_type,
        config_json=_json_load(row.config_json, {}),
        created_at=_iso(row.created_at),
    ) for row in rows]
    return DataScopeListResponse(items=items, total=len(items))


@router.get("/formal/organizers", response_model=OrganizerProfileListResponse)
def list_organizer_profiles(
    keyword: str = "",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(OrganizerProfile, User).join(User, User.id == OrganizerProfile.user_id)
    if status_filter != "all":
        query = query.filter(OrganizerProfile.status == status_filter)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            User.phone.ilike(f"%{keyword}%"),
            OrganizerProfile.brand_name.ilike(f"%{keyword}%"),
            OrganizerProfile.city.ilike(f"%{keyword}%"),
            cast(OrganizerProfile.user_id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(OrganizerProfile.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [OrganizerProfileItem(
        id=row.id,
        user_id=row.user_id,
        nickname=user.nickname or "",
        phone=user.phone or "",
        status=row.status or "pending",
        brand_name=row.brand_name or "",
        city=row.city or "",
        approved_by=row.approved_by,
        approved_at=_iso(row.approved_at),
        note=row.note or "",
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    ) for row, user in rows]
    return OrganizerProfileListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/agents", response_model=AgentProfileListResponse)
def list_agent_profiles(
    keyword: str = "",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AgentProfile, User).join(User, User.id == AgentProfile.user_id)
    if status_filter != "all":
        query = query.filter(AgentProfile.status == status_filter)
    if keyword:
        query = query.filter(or_(
            User.nickname.ilike(f"%{keyword}%"),
            User.phone.ilike(f"%{keyword}%"),
            AgentProfile.agent_code.ilike(f"%{keyword}%"),
            AgentProfile.identity_label.ilike(f"%{keyword}%"),
            cast(AgentProfile.user_id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(AgentProfile.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_agent_profile_item(row, user) for row, user in rows]
    return AgentProfileListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/referral-bindings", response_model=ReferralBindingListResponse)
def list_referral_bindings(
    keyword: str = "",
    binding_type: str = "all",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ReferralBinding)
    if binding_type != "all":
        query = query.filter(ReferralBinding.binding_type == binding_type)
    if status_filter != "all":
        query = query.filter(ReferralBinding.status == status_filter)
    if keyword:
        query = query.filter(or_(
            ReferralBinding.source_code.ilike(f"%{keyword}%"),
            ReferralBinding.campaign_code.ilike(f"%{keyword}%"),
            cast(ReferralBinding.invited_user_id, String).ilike(f"%{keyword}%"),
            cast(ReferralBinding.inviter_user_id, String).ilike(f"%{keyword}%")
        ))
    total = query.count()
    rows = query.order_by(ReferralBinding.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_ids = list({row.invited_user_id for row in rows} | {row.inviter_user_id for row in rows})
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = [_build_referral_binding_item(row, user_map) for row in rows]
    return ReferralBindingListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/agent-team-overview")
def get_agent_team_overview(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    regional_count = db.query(sa_func.count(AgentProfile.id)).filter(AgentProfile.agent_type == "regional_partner").scalar() or 0
    promoter_count = db.query(sa_func.count(AgentProfile.id)).filter(AgentProfile.agent_type == "promoter").scalar() or 0
    active_bindings = db.query(sa_func.count(ReferralBinding.id)).filter(
        ReferralBinding.attribution_status == "active",
        ReferralBinding.locked_until >= datetime.now(timezone.utc),
    ).scalar() or 0
    frozen_bonus = db.query(sa_func.coalesce(sa_func.sum(AgentTeamManagementBonusLedger.bonus_amount), 0)).filter(
        AgentTeamManagementBonusLedger.settlement_status == "frozen"
    ).scalar() or 0
    settled_bonus = db.query(sa_func.coalesce(sa_func.sum(AgentTeamManagementBonusLedger.bonus_amount), 0)).filter(
        AgentTeamManagementBonusLedger.settlement_status == "settled"
    ).scalar() or 0
    return {
        "regionalPartnerCount": int(regional_count),
        "promoterCount": int(promoter_count),
        "activeBindingCount": int(active_bindings),
        "lockDays": 180,
        "managementBaseRate": 10,
        "frozenManagementBonus": float(frozen_bonus or 0),
        "settledManagementBonus": float(settled_bonus or 0),
    }


@router.get("/formal/agent-team-management-bonuses", response_model=AgentTeamManagementBonusLedgerListResponse)
def list_agent_team_management_bonuses(
    quarter: str = "all",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AgentTeamManagementBonusLedger)
    if quarter != "all":
        query = query.filter(AgentTeamManagementBonusLedger.quarter == quarter)
    if status_filter != "all":
        query = query.filter(AgentTeamManagementBonusLedger.settlement_status == status_filter)
    total = query.count()
    rows = query.order_by(AgentTeamManagementBonusLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_ids = list({r.regional_partner_user_id for r in rows} | {r.promoter_user_id for r in rows} | {r.invited_user_id for r in rows if r.invited_user_id})
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = []
    for row in rows:
        items.append(AgentTeamManagementBonusLedgerItem(
            id=row.id,
            regional_partner_user_id=row.regional_partner_user_id,
            regional_partner_name=(user_map.get(row.regional_partner_user_id).nickname if user_map.get(row.regional_partner_user_id) else ""),
            promoter_user_id=row.promoter_user_id,
            promoter_name=(user_map.get(row.promoter_user_id).nickname if user_map.get(row.promoter_user_id) else ""),
            invited_user_id=row.invited_user_id,
            invited_user_name=(user_map.get(row.invited_user_id).nickname if row.invited_user_id and user_map.get(row.invited_user_id) else ""),
            source_order_type=row.source_order_type or "",
            source_order_id=row.source_order_id or "",
            source_commission_ledger_id=row.source_commission_ledger_id,
            base_amount=float(row.base_amount or 0),
            base_rate=float(row.base_rate or 10),
            performance_rate=float(row.performance_rate or 0),
            bonus_amount=float(row.bonus_amount or 0),
            quarter=row.quarter or "",
            settlement_status=row.settlement_status or "frozen",
            settlement_batch_no=row.settlement_batch_no or "",
            occurred_at=_iso(row.occurred_at),
            eligible_at=_iso(row.eligible_at),
            settled_at=_iso(row.settled_at),
            reversed_at=_iso(row.reversed_at),
            reverse_reason=row.reverse_reason or "",
            business_key=row.business_key or "",
            note=row.note or "",
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        ))
    return AgentTeamManagementBonusLedgerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/revenue-share-rules", response_model=RevenueShareRuleListResponse)
def list_revenue_share_rules(
    target_type: str = "all",
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(RevenueShareRule)
    if target_type != "all":
        query = query.filter(RevenueShareRule.target_type == target_type)
    if status_filter != "all":
        query = query.filter(RevenueShareRule.effective_status == status_filter)
    total = query.count()
    rows = query.order_by(RevenueShareRule.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_revenue_share_rule_item(row) for row in rows]
    return RevenueShareRuleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/agent-commissions", response_model=AgentCommissionLedgerListResponse)
def list_agent_commission_ledgers(
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AgentCommissionLedger)
    if status_filter != "all":
        query = query.filter(AgentCommissionLedger.settlement_status == status_filter)
    total = query.count()
    rows = query.order_by(AgentCommissionLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_ids = list({row.agent_user_id for row in rows} | {row.invited_user_id for row in rows})
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = []
    for row in rows:
        items.append(AgentCommissionLedgerItem(
            id=row.id,
            agent_user_id=row.agent_user_id,
            agent_name=(user_map.get(row.agent_user_id).nickname if user_map.get(row.agent_user_id) else ""),
            invited_user_id=row.invited_user_id,
            invited_user_name=(user_map.get(row.invited_user_id).nickname if user_map.get(row.invited_user_id) else ""),
            binding_id=row.binding_id,
            order_type=row.order_type or "",
            source_order_id=row.source_order_id or "",
            source_registration_id=row.source_registration_id,
            owner_type_snapshot=row.owner_type_snapshot or "official",
            product_type_snapshot=row.product_type_snapshot or "",
            target_name_snapshot=row.target_name_snapshot or "",
            base_amount=float(row.base_amount) if row.base_amount else 0,
            commission_rate=float(row.commission_rate) if row.commission_rate is not None else None,
            commission_amount=float(row.commission_amount) if row.commission_amount else 0,
            settlement_status=row.settlement_status or "pending",
            settlement_batch_no=row.settlement_batch_no or "",
            rule_id=row.rule_id,
            business_key=row.business_key or "",
            occurred_at=_iso(row.occurred_at),
            confirmed_at=_iso(row.confirmed_at),
            settled_at=_iso(row.settled_at),
            reversed_at=_iso(row.reversed_at),
            reverse_reason=row.reverse_reason or "",
            idempotency_key=row.idempotency_key or "",
            note=row.note or "",
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        ))
    return AgentCommissionLedgerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/user-referral-rewards", response_model=UserReferralRewardLedgerListResponse)
def list_user_referral_reward_ledgers(
    status_filter: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(UserReferralRewardLedger)
    if status_filter != "all":
        query = query.filter(UserReferralRewardLedger.reward_status == status_filter)
    total = query.count()
    rows = query.order_by(UserReferralRewardLedger.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_ids = list({row.inviter_user_id for row in rows} | {row.invited_user_id for row in rows})
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = []
    for row in rows:
        items.append(UserReferralRewardLedgerItem(
            id=row.id,
            inviter_user_id=row.inviter_user_id,
            inviter_user_name=(user_map.get(row.inviter_user_id).nickname if user_map.get(row.inviter_user_id) else ""),
            invited_user_id=row.invited_user_id,
            invited_user_name=(user_map.get(row.invited_user_id).nickname if user_map.get(row.invited_user_id) else ""),
            binding_id=row.binding_id,
            first_order_registration_id=row.first_order_registration_id,
            reward_type=row.reward_type or "cash",
            reward_amount_cash=float(row.reward_amount_cash) if row.reward_amount_cash else 0,
            reward_amount_points=row.reward_amount_points or 0,
            reward_amount_coupon=row.reward_amount_coupon or 0,
            reward_status=row.reward_status or "pending",
            eligible_biz_type=row.eligible_biz_type or "",
            eligible_product_type=row.eligible_product_type or "",
            owner_type_snapshot=row.owner_type_snapshot or "official",
            product_type_snapshot=row.product_type_snapshot or "",
            target_name_snapshot=row.target_name_snapshot or "",
            rule_id=row.rule_id,
            business_key=row.business_key or "",
            granted_at=_iso(row.granted_at),
            reversed_at=_iso(row.reversed_at),
            reverse_reason=row.reverse_reason or "",
            idempotency_key=row.idempotency_key or "",
            note=row.note or "",
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        ))
    return UserReferralRewardLedgerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/agent-wallets", response_model=AgentWalletAccountListResponse)
def list_agent_wallet_accounts(
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AgentWalletAccount)
    total = query.count()
    rows = query.order_by(AgentWalletAccount.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    user_ids = [row.user_id for row in rows]
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = [AgentWalletAccountItem(
        id=row.id,
        user_id=row.user_id,
        user_name=(user_map.get(row.user_id).nickname if user_map.get(row.user_id) else ""),
        account_type=row.account_type or "agent_commission",
        total_earned=float(row.total_earned) if row.total_earned else 0,
        total_settled=float(row.total_settled) if row.total_settled else 0,
        total_withdrawn=float(row.total_withdrawn) if row.total_withdrawn else 0,
        withdrawable_balance=float(row.withdrawable_balance) if row.withdrawable_balance else 0,
        frozen_balance=float(row.frozen_balance) if row.frozen_balance else 0,
        updated_at=_iso(row.updated_at),
    ) for row in rows]
    return AgentWalletAccountListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    biz_type: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if biz_type != "all":
        query = query.filter(AuditLog.biz_type == biz_type)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [AuditLogItem(
        id=row.id,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        action_code=row.action_code,
        target_type=row.target_type or "",
        target_id=row.target_id or "",
        biz_type=row.biz_type,
        request_id=row.request_id or "",
        idempotency_key=row.idempotency_key or "",
        remark=row.remark or "",
        ip=row.ip or "",
        user_agent=row.user_agent or "",
        created_at=_iso(row.created_at),
    ) for row in rows]
    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/formal/idempotency-records", response_model=IdempotencyRecordListResponse)
def list_idempotency_records(
    biz_type: str = "all",
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(IdempotencyRecord)
    if biz_type != "all":
        query = query.filter(IdempotencyRecord.biz_type == biz_type)
    total = query.count()
    rows = query.order_by(IdempotencyRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [IdempotencyRecordItem(
        id=row.id,
        biz_type=row.biz_type,
        biz_key=row.biz_key,
        idempotency_key=row.idempotency_key,
        request_hash=row.request_hash or "",
        status=row.status or "processing",
        expired_at=_iso(row.expired_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    ) for row in rows]
    return IdempotencyRecordListResponse(items=items, total=total, page=page, page_size=page_size)

