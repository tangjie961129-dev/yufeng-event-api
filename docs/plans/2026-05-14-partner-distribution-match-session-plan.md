# G2 计划：首轮最小闭环

业务参数：
- First Touch 锁客期：180 天
- 区域合伙人团队管理奖：10% 固定，季度冻结

改动范围：
1. 后端模型
   - permission_distribution.py: 扩展 AgentProfile/ReferralBinding，新增 AgentTeamManagementBonusLedger。
   - love_models.py: 新增 MatchSession/MatchRoomInvitation。
   - models/__init__.py: 导出新模型。
2. 后端 schema/router
   - permission_distribution schema 增加字段和管理奖 item/list。
   - admin_permission_distribution 增加 team overview、management-bonuses 列表，完善 agent/referral 输出。
   - love.py 增加真实感 signals、sessionId、matchSession，并新增 confirm/refund 接口。
3. Admin Web
   - 新增 PartnerSystemView.vue，展示区域合伙人/推广员/归因/季度管理奖。
   - router/index.js 和 DashboardLayout.vue 增加菜单。
4. 验证
   - python -m compileall app
   - npm run build

不在首轮做：
- 真实微信支付自动分账。
- 真正企业微信自动建三人群。
- 私域7天任务台完整实现。
