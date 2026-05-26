# 屿风权限管理 + 分销奖励系统正式落地方案 v1（今晚做到第2步）

更新时间：2026-05-04
项目目录：/home/tangjie/yufeng-event-api
目标范围：
1. 权限管理系统（RBAC + 数据权限）
2. 分销与奖励系统（一级代理长期返佣 + 普通用户一级首单奖励）

---

## 一、今晚交付边界

根据当前要求，今晚只做到前两步：

### 已做到的目标
1. 梳理现状与目标差距
2. 完成正式数据模型设计，并明确“双账本拆分方案”

### 今晚不做的内容
1. 不写最终业务规则代码
2. 不落地绑定/结算/冲正接口
3. 不实现最终幂等流程
4. 不实现最终审计日志流水
5. 不接真实小程序 API

说明：明天等你补充“具体规则”后，再进入第 3 步：状态机 + 规则 + API 落地。

---

## 二、当前已有基础（现状）

当前后端已经存在的基础能力：

### 1. 后台权限 P0
已有：
- admin_role_permissions
- AdminUser.role
- /api/admin/permissions/me
- /api/admin/admin-users

说明：
- 这是“后台管理员角色权限”的轻量版
- 还不是完整 RBAC
- 还没有数据权限（data scope）

### 2. 分销 P0
已有表：
- distributor_profiles
- distributor_invites
- commission_ledgers
- withdrawal_requests

已有后台接口：
- /api/admin/distributors
- /api/admin/commissions
- /api/admin/withdrawals
- /api/admin/withdrawals/{id}/review

说明：
- 这是单账本分销原型
- 不能满足“一级代理长期返佣”和“普通用户一级首单奖励”并行
- 也不满足可审计、幂等、可冲正的正式要求

---

## 三、当前系统与新目标的核心差距

### 差距 A：角色体系不完整
当前只有：
- admin（后台管理员）
- user（普通用户）
- distributor（分销员/代理雏形）

但目标至少需要明确分开：
- 普通用户
- 主理人（organizer）
- 一级代理（agent）
- 后台管理员（admin）

必须保证：
- 主理人体系独立于代理体系
- 普通用户默认不可访问主理人后台
- 普通用户默认不可访问代理后台
- 主理人不天然等于代理
- 代理不天然等于主理人

### 差距 B：只有单账本，没有双账本
当前只有：
- commission_ledgers

但目标需要拆成两套独立业务语义：
1. 一级代理长期返佣
2. 普通用户一级首单奖励

两者不能混在一张“commission”概念里，否则会导致：
- 财务口径混乱
- 审核口径混乱
- 前端展示混乱
- 冲正逻辑混乱

### 差距 C：没有审计日志
目标要求以下行为必须可审计：
- 审核
- 赋权
- 绑定
- 返佣
- 奖励
- 冲正

当前没有正式 audit log。

### 差距 D：没有幂等保证
目标要求所有关键绑定请求都必须幂等。
当前系统没有统一：
- idempotency_key
- business_unique_key
- request fingerprint
- duplicate protection

### 差距 E：没有数据权限模型
目前后台接口大多是“有权限就看全部”。
目标需要：
- 角色权限（能不能做）
- 数据权限（能看哪些数据）

### 差距 F：没有正式状态机
当前提现有部分状态，但系统整体没有定义：
- 绑定状态
- 奖励状态
- 返佣状态
- 冲正状态
- 审核状态

---

## 四、正式目标架构（高层）

本系统建议拆为 4 层：

### 1. 身份层 Identity
描述“你是谁”：
- user
- organizer
- agent
- admin

### 2. 权限层 Access Control
描述“你能做什么”：
- RBAC 角色权限
- 数据权限 data scope

### 3. 关系层 Relationship
描述“你和谁绑定”：
- 主理人资格
- 代理资格
- 邀请绑定关系

### 4. 账务层 Ledger
描述“发生了什么钱/奖励”：
- agent commission ledger
- referral reward ledger
- withdrawal ledger
- reversal ledger

这 4 层必须分离，不能把“身份、权限、关系、账务”都揉进 distributor_profiles 一张表里。

---

## 五、正式数据模型设计（今晚重点）

下面是建议的正式表设计。今晚不一定立刻建表，但模型必须先定清楚。

### A. 权限系统（RBAC + 数据权限）

#### 1. roles
用途：系统角色定义

建议字段：
- id
- code：super_admin / finance_admin / operator / organizer / agent / user
- name
- status
- created_at
- updated_at

说明：
- user / organizer / agent 是业务身份角色
- super_admin / finance_admin / operator 是后台管理角色
- 可并存，但作用域不同

#### 2. permissions
用途：权限点定义

建议字段：
- id
- code
- name
- module
- action
- created_at

示例：
- admin_users.manage
- distribution.view
- distribution.withdraw.review
- agent.apply.review
- reward.reverse
- audit.view
- organizer.manage

#### 3. role_permissions
用途：角色与权限点映射

建议字段：
- id
- role_code
- permission_code
- created_at

#### 4. user_role_bindings
用途：用户/后台账号拥有哪些角色

建议字段：
- id
- principal_type：admin_user / user
- principal_id
- role_code
- source：system/manual/audit_approved
- status
- granted_by
- granted_at
- revoked_by
- revoked_at

说明：
- 不要只靠 user 表或 admin_user 表上的单个 role 字段
- 单字段 role 适合作缓存视图，不适合作正式权限真源

#### 5. data_scopes
用途：数据权限范围定义

建议字段：
- id
- role_code
- scope_code：all / self / assigned / city / organization / none
- resource_type：withdrawal / commission / reward / organizer / user
- config_json
- created_at

用途示例：
- finance_admin 可看全部提现
- operator 只能看分配给自己的审核池
- organizer 只能看自己的活动数据
- agent 只能看自己的返佣和下级邀请数据

---

### B. 主理人与代理体系解耦

#### 6. organizer_profiles
用途：主理人档案

建议字段：
- id
- user_id
- status：pending/approved/rejected/disabled
- brand_name
- city
- approved_by
- approved_at
- note
- created_at
- updated_at

说明：
- 主理人资格独立
- 不和代理资格共表

#### 7. agent_profiles
用途：一级代理档案

建议字段：
- id
- user_id
- agent_code
- level：level_1
- status：pending/approved/rejected/disabled
- approved_by
- approved_at
- reject_reason
- bind_channel
- note
- created_at
- updated_at

说明：
- 这是“一级代理长期返佣”的主体
- 不复用 distributor_profiles，建议新建或迁移升级

结论：
- organizer_profiles 管主理人
- agent_profiles 管代理
- 两者互不替代

---

### C. 邀请绑定关系层

#### 8. referral_bindings
用途：普通用户与邀请人的绑定关系

建议字段：
- id
- invited_user_id
- inviter_user_id
- inviter_type：agent / user
- binding_type：agent_referral / first_order_reward
- source_channel：invite_code / qr / manual / operation
- source_code
- status：pending / bound / locked / invalid / reversed
- first_order_registration_id
- bound_at
- locked_at
- invalidated_at
- invalid_reason
- idempotency_key
- created_at
- updated_at

关键设计：
- 一个被邀请用户只能存在有效一级绑定
- 但要明确它属于哪种业务语义：
  - agent_referral
  - first_order_reward

说明：
- 如果最终规则要求“一个用户既可落入代理长期返佣，又可落入普通用户首单奖励”，则不能用这一张表直接硬限制唯一；需要拆成两张绑定表或增加 relationship bucket。
- 这点明天必须由你补规则后最终拍板。

今晚先定推荐方案：
- 使用统一关系表 referral_bindings
- 用 binding_type 强制区分业务语义
- 再通过唯一约束决定同一 invited_user 在每种 binding_type 下是否只能有一条有效记录

建议唯一约束：
- unique(invited_user_id, binding_type, active_flag)
  或
- 通过 status + partial unique index 实现

---

### D. 双账本设计（今晚核心）

这是今晚最重要的第 2 步。

必须拆为两本账：

#### 9. agent_commission_ledgers
用途：一级代理长期返佣账本

适用对象：
- 一级代理 agent

适用场景：
- 被邀请用户后续符合规则的订单
- 按长期返佣规则持续累计

建议字段：
- id
- agent_user_id
- invited_user_id
- binding_id
- order_type
- source_order_id
- source_registration_id
- base_amount
- commission_rate
- commission_amount
- settlement_status：pending / confirmed / settled / reversed
- settlement_batch_no
- occurred_at
- confirmed_at
- settled_at
- reversed_at
- reverse_reason
- reverse_ref_id
- idempotency_key
- business_key
- note
- created_at
- updated_at

说明：
- 这是“长期返佣”专用账本
- 不能混入普通用户首单奖励

#### 10. user_referral_reward_ledgers
用途：普通用户一级首单奖励账本

适用对象：
- 普通用户 inviter

适用场景：
- 仅首单奖励
- 非长期返佣

建议字段：
- id
- inviter_user_id
- invited_user_id
- binding_id
- first_order_registration_id
- reward_type：cash / points / coupon / mixed
- reward_amount_cash
- reward_amount_points
- reward_amount_coupon
- reward_status：pending / confirmed / granted / reversed
- granted_at
- reversed_at
- reverse_reason
- reverse_ref_id
- idempotency_key
- business_key
- note
- created_at
- updated_at

说明：
- 首单奖励单独记账
- 就算未来前端统一叫“邀请奖励”，底层账务也必须单独存

#### 11. 为什么必须拆成两张账表，而不是一张大而全 ledger
原因：
1. 财务口径不同
2. 结算规则不同
3. 状态机不同
4. 展示对象不同
5. 冲正规则可能不同
6. 审核主体不同
7. 后续统计口径会更清晰

结论：
- 一级代理长期返佣：agent_commission_ledgers
- 普通用户一级首单奖励：user_referral_reward_ledgers

这就是今晚第 2 步的核心交付。

---

### E. 提现与余额体系

#### 12. agent_wallet_accounts
用途：代理可提现余额账户

建议字段：
- id
- user_id
- account_type：agent_commission
- total_earned
- total_settled
- total_withdrawn
- withdrawable_balance
- frozen_balance
- updated_at

说明：
- 提现应只面向 agent_commission 余额
- 普通用户首单奖励如果是现金，也要看规则决定是否进入 user wallet，不能默认复用代理钱包

#### 13. agent_withdrawal_requests
用途：一级代理提现申请

建议字段：
- id
- agent_user_id
- amount
- account_name
- account_type
- account_no
- status：pending / approved / paid / rejected / cancelled
- reviewed_by
- reviewed_at
- paid_at
- reject_reason
- idempotency_key
- created_at
- updated_at

说明：
- 当前 withdrawal_requests 更像 P0 表
- 后续建议迁移为 agent_withdrawal_requests，语义更清晰

---

### F. 审计日志（正式必备，今晚先设计）

#### 14. audit_logs
用途：所有关键动作留痕

建议字段：
- id
- actor_type：admin_user / user / system / job
- actor_id
- action_code
- target_type
- target_id
- biz_type：rbac / organizer / agent / referral / commission / reward / withdrawal
- before_json
- after_json
- request_id
- idempotency_key
- remark
- ip
- user_agent
- created_at

必须覆盖的动作：
- 角色赋权
- 角色撤权
- 主理人审核
- 代理审核
- 邀请绑定
- 奖励发放
- 佣金结算
- 提现审核
- 提现打款
- 冲正

---

### G. 幂等记录（正式必备，今晚先设计）

#### 15. idempotency_records
用途：关键请求幂等保证

建议字段：
- id
- biz_type
- biz_key
- idempotency_key
- request_hash
- status：processing / success / failed
- response_snapshot
- expired_at
- created_at
- updated_at

应用场景：
- 绑定邀请码
- 首单奖励发放
- 代理返佣结算
- 提现申请
- 提现审核
- 冲正

---

## 六、双账本拆分方案（今晚正式结论）

### 结论一
“一级代理长期返佣”与“普通用户一级首单奖励”必须拆分为两套独立账本，不共用一张 ledger。

### 结论二
两套账本分别绑定不同主体：
- 一级代理长期返佣 → agent_profiles / agent_wallet_accounts / agent_commission_ledgers
- 普通用户首单奖励 → user_referral_reward_ledgers

### 结论三
两套账本即使都来源于“邀请关系”，也不能复用同一状态字段和同一结算逻辑。

### 结论四
前端可以统一展示为“邀请奖励/分销中心”，但后端必须保持双账独立。

---

## 七、对现有 P0 表的处理建议

### 1. admin_role_permissions
处理：
- 可保留，作为 role_permissions 的 P0 数据来源
- 后续建议升级为正式 roles + permissions + role_permissions 三表

### 2. distributor_profiles
处理：
- 不建议继续作为最终正式表
- 建议迁移为 agent_profiles
- 如要兼容旧数据，可先保留，再写迁移脚本

### 3. distributor_invites
处理：
- 建议迁移升级为 referral_bindings
- 原表结构不足以承载 binding_type / 状态机 / 幂等 / 审计

### 4. commission_ledgers
处理：
- 建议废弃为正式主账
- 拆分迁移到：
  - agent_commission_ledgers
  - user_referral_reward_ledgers

### 5. withdrawal_requests
处理：
- 建议升级为 agent_withdrawal_requests
- 语义明确只服务代理提现

---

## 八、明天待你确认的关键规则点

这些规则今晚先不拍板，等你明天给业务规则：

### 1. 邀请绑定规则
- 普通用户是否也能邀请普通用户？
- 一个被邀请用户能否同时命中“代理返佣关系”和“普通用户首单奖励关系”？
- 绑定是否允许覆盖？
- 绑定何时锁定？注册时？首单前？支付后？

### 2. 首单定义
- 首单按“第一笔支付成功订单”还是“第一笔有效核销订单”？
- 钱包充值算不算首单？
- 免费活动算不算首单？

### 3. 一级代理长期返佣规则
- 是所有后续订单都返，还是限定活动报名？
- 钱包充值是否参与返佣？
- 退款时是否全额冲正？

### 4. 普通用户首单奖励规则
- 奖励给现金、积分、优惠券还是组合？
- 首单奖励是否需要审核？
- 奖励是否立即到账？

### 5. 提现规则
- 仅代理可提现吗？
- 普通用户首单现金奖励是否能提现，还是只入用户钱包？
- 最低提现门槛是多少？

### 6. 数据权限规则
- finance_admin 能否看全部？
- operator 是按池子看，还是按城市看？
- agent 是否有独立后台，还是只在小程序侧看自己的数据？

---

## 八点五、2026-05-04 已新增确认规则（用户最新口径）

以下规则已由业务口头确认，可直接进入后续设计与开发：

### 1. 邀请绑定入口：四种方式都算有效来源
支持以下绑定来源：
- 分享小程序
- 分享链接
- 分享二维码
- 注册时直接绑定推荐人 ID

因此 referral_bindings / 邀请绑定模型中，source_channel 必须至少支持：
- mini_program
- link
- qr_code
- referrer_id

并保留 source_code / campaign_code / scene_value 一类字段，用于记录：
- 二维码场景值
- 邀请码
- 链接参数
- 推荐人 ID
- 活动投放批次

### 2. 分佣范围：只分官方商品与官方活动
明确排除主理人：
- 所有分佣只针对平台官方商品与平台官方活动
- 主理人活动与主理人结算体系完全独立
- 主理人不参与代理返佣，也不参与普通用户首单奖励计算

因此后续订单/商品模型必须具备至少一个清晰字段用于区分：
- official
- organizer

推荐新增统一业务归属字段：
- owner_type = official / organizer

只有 owner_type = official 的订单，才进入：
- agent_commission_ledgers
- user_referral_reward_ledgers

### 3. 首单定义：仅限平台 AI 匹配会员首次消费
普通用户一级首单奖励的“首单”口径明确为：
- 仅统计平台 AI 匹配会员的首次消费
- 普通活动报名不算首单奖励触发源
- 普通商品消费不算首单奖励触发源
- 主理人相关消费也不算

因此后续需要单独定义一个可识别的业务对象，例如：
- product_type = ai_match_membership
或
- biz_type = ai_match_membership_purchase

user_referral_reward_ledgers 只对这一类订单生效。

### 4. 一级代理长期收益：由后台按商品/活动配置比例
一级代理不是固定写死比例，而是后台可调控：
- 每种官方商品可单独配置代理分润比例
- 每种官方活动可单独配置代理分润比例
- 后续每上架一个商品，都要可配置分润比例
- 平台需要一个专门的管理界面维护这套规则

因此不能只保留全局 commission_rate，必须升级为“按商品/活动维度”的分润配置体系。

推荐新增：
- revenue_share_rules（或 commission_rule_items）

建议字段：
- id
- target_type：official_product / official_event
- target_id
- target_name_snapshot
- agent_level：level_1
- commission_mode：fixed_rate / fixed_amount
- commission_rate
- commission_amount
- effective_status
- effective_from
- effective_to
- created_by
- updated_by
- created_at
- updated_at

说明：
- 官方商品：按 SKU / 商品 ID 配置
- 官方活动：按活动 ID 配置
- 订单结算时固化快照，避免后改比例影响历史账单

### 5. 一级代理角色定位：共享合伙人
业务语义上，一级代理 = 共享合伙人。

这意味着：
- agent_profiles 中建议保留 role_name_snapshot 或 identity_label
- 前端/后台展示时可统一称为：共享合伙人
- 但底层技术角色仍建议保留 agent，避免和 organizer / admin 混淆

---

## 九、基于最新规则的模型修订建议

### 1. referral_bindings 需要补的字段
在原建议基础上增加/强调：
- source_channel：mini_program / link / qr_code / referrer_id
- source_code：邀请码、scene 值、推荐人编码、链接参数快照
- landing_page
- campaign_code
- binding_context_json

### 2. 订单/商品归属必须可区分 official / organizer
无论是活动、商品、会员服务，后续凡涉及分佣判断，必须能识别归属：
- owner_type = official / organizer

若现有 event 表不能表达，建议后续补：
- owner_type
- settlement_system

例如：
- official + platform_distribution
- organizer + organizer_settlement

### 3. 首单奖励账只对 AI 匹配会员订单生效
user_referral_reward_ledgers 建议增加字段：
- eligible_biz_type
- eligible_product_type

并固定首期只允许：
- ai_match_membership_purchase

### 4. 代理长期返佣配置必须抽成“规则表”
现有 CommissionSetting 只有全局 rate/min_fee/max_fee，不够。
后续必须拆成：
- 全局默认配置（可选）
- 商品/活动级分润规则明细表

后台需要：
- 分润规则列表页
- 新增/编辑规则页
- 按官方商品配置
- 按官方活动配置
- 启停规则
- 生效时间管理

### 5. 结算计算必须保存规则快照
无论代理返佣还是首单奖励，流水里建议都固化：
- rule_id
- rule_snapshot_json
- owner_type_snapshot
- product_type_snapshot
- target_name_snapshot

否则后期修改规则会影响历史对账。

---

## 十、今晚的最终结论

今晚已经把“正式落地方案”的第 2 步定清楚：

### 已确认结论
1. 主理人体系必须独立于代理体系
2. 后端必须从单账本升级为双账本
3. 双账本拆分为：
   - agent_commission_ledgers
   - user_referral_reward_ledgers
4. 现有 P0 distributor / commission / withdrawal 结构不能直接作为正式终版
5. 正式系统必须补齐：
   - roles / permissions / user_role_bindings / data_scopes
   - organizer_profiles / agent_profiles
   - referral_bindings
   - audit_logs
   - idempotency_records

### 今晚还没做
1. 未写迁移 SQL
2. 未改 ORM 实体
3. 未改接口
4. 未做状态机
5. 未做幂等实现
6. 未做审计实现

---

## 十、明天的推荐起手顺序

明天你给出业务规则后，建议我按这个顺序继续：

1. 定规则表与状态机
2. 出迁移方案（旧表 -> 新表）
3. 改 SQLAlchemy models
4. 改 schemas
5. 先做后台审核与查询接口
6. 再做用户侧绑定/奖励 API
7. 最后把小程序前端从 mock 接到真实接口

---

## 十一、状态说明（给业务确认）

当前状态可以准确描述为：
- 前端分销页：演示版已完成
- 后端分销：P0 原型已完成
- 正式权限 + 双账本架构：今晚已完成设计方案，但尚未进入代码落地
