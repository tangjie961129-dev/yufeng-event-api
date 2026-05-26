# G1 探索：合伙人分销与 AI 匹配包间闭环

已读取：
- app/models/permission_distribution.py
- app/schemas/permission_distribution.py
- app/routers/admin_permission_distribution.py
- app/models/love_models.py
- app/routers/love.py
- app/services/matching_service.py
- app/models/user.py
- app/models/__init__.py
- app/main.py
- yufeng-admin-web/src/router/index.js
- yufeng-admin-web/src/views/DashboardLayout.vue
- skill: yufeng-backend-driven-architecture references/implementation-status-2026-05-14.md
- skill: yufeng-backend-driven-architecture references/partner-distribution-private-ai-strategy-2026-05-14.md

结论：
- 正式分销模型已有 AgentProfile/ReferralBinding/RevenueShareRule/AgentCommissionLedger/AgentWalletAccount/AgentWithdrawalRequest。
- 需要扩展 regional_partner/promoter、180天锁客、10%季度管理奖冻结池。
- AI 匹配当前 /api/love/match 直接扣 current_user.match_credits，需改为生成 match_session，并提供 confirm/refund 状态接口。
- Admin Web 当前只有旧分销员/佣金/提现页面，需要新增合伙人体系页面。
