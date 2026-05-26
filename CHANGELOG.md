# 屿风活动报名 API - 变更日志

## 2026-05-26
- 🎬 项目初始化 Git
- 🔧 partner_router: 渠道主登录改为手机号+密码，注册加密码二次确认
- 🔧 partner_router: 注册页去掉微信号字段
- 🔧 partner_router: 修复 onkeydown 单引号嵌套导致页面空白问题
- 🔧 partner_router: _ADMIN_PASSWORD 从 *** 改为 yufeng2026
- 🆕 channel_admin.html: 独立页面文件，避免 HTML 内嵌 Python 字符串的转义问题
- 🆕 partner_page.html: 渠道主注册/登录独立页面文件
- 🔧 member_profiles: 表从22字段重建为43字段，覆盖全部26项表单字段
- 🆕 huxuan_profiles: 煎面外部合作表(1083条, 全35字段+随机昵称)
- 🗑️ users/member_profiles: 清理旧互选导入的假数据
- 🔧 cron: generate_posts.py 数据源改为 PG(member_profiles+huxuan_profiles)
- 🔧 cron: 推送时间改为 10:00/14:00/20:00
- 🆕 cron: generate_review.py + deliver_review.py 朋友圈预览机制
