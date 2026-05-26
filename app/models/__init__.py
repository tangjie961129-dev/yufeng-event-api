"""数据库模型文件
"""
from app.models.user import User
from app.models.admin import AdminUser
from app.models.event import Event, EventRegistration, EventFavorite, EventReview, OrganizerCertification, CommissionSetting
from app.models.registration_link import RegistrationLink
from app.models.member_profile import MemberProfile
from app.models.love_models import MatchCredit, MatchSession, MatchRoomInvitation, BoyfriendState, BoyfriendMessage
from app.models.permission_distribution import (
    AdminRolePermission,
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
    DistributorProfile,
    DistributorInvite,
    CommissionLedger,
    WithdrawalRequest,
)
from app.models.course import Course, UserCourseProgress
from app.models.quiz import Quiz, QuizQuestion, QuizResult, QuizSubmission
from app.models.admin_ops import OpsTask, AiUsageLog, OpsDailyReview
from app.models.cms import (
    CmsCategory,
    CmsBanner,
    CmsPageWidget,
    CmsAnnouncement,
    MemberTag,
    MemberProfileTag,
)
from app.models.cooperation import CooperationApplication

__all__ = [
    "User",
    "MatchCredit",
    "MatchSession",
    "MatchRoomInvitation",
    "BoyfriendState",
    "BoyfriendMessage",
    "AdminUser",
    "Event",
    "EventRegistration",
    "EventFavorite",
    "EventReview",
    "OrganizerCertification",
    "CommissionSetting",
    "AdminRolePermission",
    "Role",
    "Permission",
    "RolePermission",
    "UserRoleBinding",
    "DataScope",
    "RegistrationLink",
    "MemberProfile",
    "OrganizerProfile",
    "AgentProfile",
    "ReferralBinding",
    "RevenueShareRule",
    "AgentCommissionLedger",
    "AgentTeamManagementBonusLedger",
    "UserReferralRewardLedger",
    "AgentWalletAccount",
    "AgentWithdrawalRequest",
    "AuditLog",
    "IdempotencyRecord",
    "DistributorProfile",
    "DistributorInvite",
    "CommissionLedger",
    "WithdrawalRequest",
    "Course",
    "UserCourseProgress",
    "Quiz",
    "QuizQuestion",
    "QuizResult",
    "QuizSubmission",
    "CmsCategory",
    "CmsBanner",
    "CmsPageWidget",
    "CmsAnnouncement",
    "MemberTag",
    "MemberProfileTag",
    "OpsTask",
    "AiUsageLog",
    "OpsDailyReview",
    "CooperationApplication",
]
from app.models.huxuan_profile import HuxuanProfile
