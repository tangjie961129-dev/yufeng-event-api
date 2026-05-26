# 权限管理与分销系统 P0 后端设计（简版）

时间：2026-05-04
项目：yufeng-event-api

## 目标
在现有活动报名后台基础上，补齐一套“能跑”的 P0 后端结构，优先提供：
1. 管理员角色与权限声明
2. 后台账号 CRUD 基础能力
3. 分销员/代理关系建模
4. 邀请码与绑定关系
5. 佣金台账与提现申请
6. 后台查询接口，供后续 Web Admin 前端接入

## 约束
- 先兼容现有 `AdminUser.role` 字段，不做复杂 RBAC 引擎。
- 先用 SQLAlchemy `create_all()` 补新表，不在本轮引入 Alembic。
- 所有接口挂到现有 `/api/admin/*` 命名空间。
- 默认以 `super_admin` 拥有全部权限。

## P0 数据模型
- admin_role_permissions：角色-权限映射（轻量表）
- distributor_profiles：分销员档案
- distributor_invites：邀请码/邀请绑定记录
- commission_ledgers：佣金流水
- withdrawal_requests：提现申请

## P0 接口
- GET /api/admin/permissions/me
- GET /api/admin/admin-users
- POST /api/admin/admin-users
- POST /api/admin/admin-users/{id}/toggle-active
- GET /api/admin/distributors
- GET /api/admin/commissions
- GET /api/admin/withdrawals
- POST /api/admin/withdrawals/{id}/review

## 本轮不做
- 复杂多级分销结算任务
- 自动从订单实时拆佣
- 普通小程序端绑定/申请前台接口
- 财务打款回单上传

## 验证
- python -m compileall app
- 确保 main.py 已注册新路由
- 确保 models/__init__.py 已导入新模型
