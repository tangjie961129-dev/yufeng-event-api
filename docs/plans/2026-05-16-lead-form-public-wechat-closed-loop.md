# 屿风可配置登记表 + 公开引流线索闭环 Implementation Plan

> For Hermes: Use SCALE OS lightweight workflow. Explore first, plan before code, verify every deployed change.

Goal: 把当前写死在后端的企微专属登记表，升级为总后台可配置表单，并新增个人微信公开引流版：填表生成 lead_id/state，用户扫码添加企微后自动绑定 external_userid、建档、打标签、通知员工。

Architecture: 保留现有企微专属链接流程稳定运行；新增 lead_forms / lead_submissions / lead_wecom_states 等表承接公开引流；通过企微“联系我”二维码 state 把公开表单提交和后续企微外部联系人绑定；所有自动写企微的动作都提供后台 preview/retry/人工确认兜底。

Tech Stack: FastAPI, SQLAlchemy, PostgreSQL, Vue 3, Element Plus, 企业微信外部联系人/联系我接口。

---

## 0. 已确认现状

项目：/home/ubuntu/yufeng-event-api
服务：yufeng-event-api
域名：https://yufeng.team
后台前端：/home/ubuntu/yufeng-event-api/yufeng-admin-web

当前已存在：
- app/routers/wecom_oauth.py
  - REGISTER_FORM_HTML：当前硬编码 H5 登记表
  - /api/wecom/tag/register-form
  - /api/wecom/tag/register-form-submit
  - /api/wecom/tag/check-link
- app/routers/wx_kf.py
  - 企微自建应用回调
  - 员工发送“给 XXX 发链接”后生成专属 token 链接
- app/models/registration_link.py
  - registration_links 专属链接 token 表
- app/models/member_profile.py
  - member_profiles 会员档案表
- app/services/wecom.py
  - find_external_userid
  - ensure_tag_group / ensure_tag / mark_tag
  - remark_external_contact
  - evaluate_member_level
  - suggest_tags_from_form 当前主要返回 层级·S/A/B/C
- yufeng-admin-web
  - Vue3 + Element Plus
  - /api/admin baseURL
  - 已有 WecomBackfillView 的 preview-first 安全模式

重要原则：
- 不要把公开引流/客服大脑功能塞进小程序后台，放总后台 · 客服大脑。
- 现有企微专属登记链接不能被破坏。
- 自动打标签/备注是有副作用的，必须有日志、幂等和人工兜底。

---

## 1. 分阶段落地路线

### Phase 1：总后台可配置表单（不接公开引流，不写企微）

Objective: 后台能创建、编辑、预览、发布表单 schema，但不改变现有专属登记流程。

Backend files:
- Create: app/models/lead_form.py
- Create: app/schemas/lead_form.py
- Create: app/routers/admin_lead_forms.py
- Modify: app/models/__init__.py
- Modify: app/main.py

Frontend files:
- Create: yufeng-admin-web/src/views/LeadFormManageView.vue
- Modify: yufeng-admin-web/src/router/index.js
- Modify: yufeng-admin-web/src/views/DashboardLayout.vue

Tables:
- lead_forms
- lead_form_versions 推荐一起做，避免历史提交解释不了

Acceptance:
- 管理后台出现“引流表单”。
- 可创建“个人微信公开引流表单”。
- 可编辑字段、选项、必填、排序。
- 可预览。
- 可发布。
- 当前 /api/wecom/tag/register-form 不受影响。

### Phase 2：公开引流表单提交入库（不接企微二维码）

Objective: 发布后的公开表单可通过公开 URL 打开并提交，生成 lead_submissions，保存 raw_data/normalized_data/level/suggested_tags/state。

Backend files:
- Create: app/models/lead_submission.py 或继续放 app/models/lead_form.py
- Create: app/routers/public_lead_forms.py
- Create: app/routers/admin_leads.py
- Create: app/services/lead_pipeline.py
- Modify: app/main.py
- Modify: app/models/__init__.py

Frontend files:
- Create: yufeng-admin-web/src/views/LeadSubmissionView.vue
- Modify: yufeng-admin-web/src/router/index.js
- Modify: yufeng-admin-web/src/views/DashboardLayout.vue

Tables:
- lead_submissions
- lead_operation_logs

Acceptance:
- 公开链接能打开动态表单。
- 提交后 lead_submissions 有记录。
- 后台能看提交列表和详情。
- 不写企微，不建 member_profiles。

### Phase 3：企微联系我二维码 state 绑定

Objective: 公开表单提交成功后展示带 state 的企微“联系我”二维码；用户添加企微后，回调能把 lead_submissions 绑定 external_userid。

Backend files:
- Create: app/services/wecom_contact_way.py
- Modify: app/routers/public_lead_forms.py
- Modify: app/routers/wx_kf.py
- Modify: app/routers/admin_leads.py

Tables:
- lead_wecom_states 可选；也可先直接用 lead_submissions.state

Acceptance:
- 表单提交返回 qr_code_url/config_id/state。
- 用户通过该二维码加企微后，lead_submissions.external_userid 被回填。
- state 为空或匹配不到时，进入 needs_manual_match，后台人工处理。

### Phase 4：自动建档、打标签、备注、员工通知

Objective: lead 绑定 external_userid 后自动写 member_profiles、企微标签、企微备注/描述，并通知员工。

Backend files:
- Modify: app/services/lead_pipeline.py
- Modify: app/services/wecom.py 如需新增 get_contact_detail / contact_way API
- Modify: app/routers/wx_kf.py
- Modify: app/routers/admin_leads.py

Acceptance:
- lead -> member_profiles 幂等 upsert。
- 企微标签至少打 层级·S/A/B/C + 来源·公开引流/个人微信（具体标签策略可配置）。
- 企微备注/description 写入摘要。
- 员工收到通知：来源、基本资料、层级、处理建议、后台详情链接。
- 重复回调不会重复通知/重复写错状态。

### Phase 5：后台人工匹配、预览、重试、灰度开关

Objective: 为无法通过 state 精准绑定的 lead 提供后台候选匹配和人工确认；所有企微写操作可预览、可重试、可关闭自动化。

Backend files:
- Modify: app/routers/admin_leads.py
- Modify: app/services/lead_pipeline.py

Frontend files:
- Modify: yufeng-admin-web/src/views/LeadSubmissionView.vue

Acceptance:
- 后台能按 nickname/phone/wechat_id/时间窗口查候选 external_userid。
- preview-profile 不写企微。
- apply 需要二次确认。
- retry 有操作日志。
- 可按表单/渠道开启或关闭自动打标签。

---

## 2. 建议数据库结构

### lead_forms

- id SERIAL PRIMARY KEY
- slug VARCHAR(100) UNIQUE NOT NULL
- name VARCHAR(100) NOT NULL
- title VARCHAR(200) DEFAULT ''
- description TEXT DEFAULT ''
- scene VARCHAR(50) DEFAULT 'public_wechat'
- form_schema JSONB NOT NULL
- ui_schema JSONB DEFAULT '{}'
- status VARCHAR(20) DEFAULT 'draft'
- version INTEGER DEFAULT 1
- published_at TIMESTAMPTZ NULL
- created_by INTEGER NULL
- updated_by INTEGER NULL
- created_at TIMESTAMPTZ DEFAULT now()
- updated_at TIMESTAMPTZ DEFAULT now()

### lead_form_versions

- id SERIAL PRIMARY KEY
- form_id INTEGER REFERENCES lead_forms(id)
- version INTEGER NOT NULL
- form_schema JSONB NOT NULL
- ui_schema JSONB DEFAULT '{}'
- published_at TIMESTAMPTZ DEFAULT now()
- created_by INTEGER NULL
- created_at TIMESTAMPTZ DEFAULT now()
- UNIQUE(form_id, version)

### lead_submissions

- id SERIAL PRIMARY KEY
- lead_no VARCHAR(40) UNIQUE NOT NULL
- form_id INTEGER REFERENCES lead_forms(id)
- form_version INTEGER DEFAULT 1
- source VARCHAR(50) DEFAULT 'public_wechat'
- source_channel VARCHAR(100) DEFAULT ''
- source_scene VARCHAR(100) DEFAULT ''
- state VARCHAR(128) UNIQUE NOT NULL
- employee_userid VARCHAR(100) DEFAULT ''
- external_userid VARCHAR(100) NULL
- nickname VARCHAR(100) DEFAULT ''
- city VARCHAR(100) DEFAULT ''
- age INTEGER NULL
- height INTEGER NULL
- weight INTEGER NULL
- role_self VARCHAR(20) DEFAULT ''
- body_type VARCHAR(20) DEFAULT ''
- job VARCHAR(100) DEFAULT ''
- income VARCHAR(50) DEFAULT ''
- phone VARCHAR(50) DEFAULT ''
- wechat_id VARCHAR(100) DEFAULT ''
- raw_data JSONB NOT NULL
- normalized_data JSONB DEFAULT '{}'
- level VARCHAR(5) DEFAULT ''
- suggested_tags JSONB DEFAULT '[]'
- status VARCHAR(30) DEFAULT 'submitted'
- member_profile_id INTEGER NULL REFERENCES member_profiles(id)
- error_message TEXT DEFAULT ''
- submitted_at TIMESTAMPTZ DEFAULT now()
- wecom_added_at TIMESTAMPTZ NULL
- processed_at TIMESTAMPTZ NULL
- created_at TIMESTAMPTZ DEFAULT now()
- updated_at TIMESTAMPTZ DEFAULT now()

### lead_operation_logs

- id SERIAL PRIMARY KEY
- lead_id INTEGER REFERENCES lead_submissions(id)
- action VARCHAR(50)
- actor_type VARCHAR(20) DEFAULT 'system'
- actor_id VARCHAR(100) DEFAULT ''
- request_snapshot JSONB DEFAULT '{}'
- result_snapshot JSONB DEFAULT '{}'
- success BOOLEAN DEFAULT true
- error_message TEXT DEFAULT ''
- created_at TIMESTAMPTZ DEFAULT now()

### lead_wecom_states 可选

- id SERIAL PRIMARY KEY
- state VARCHAR(128) UNIQUE NOT NULL
- lead_id INTEGER REFERENCES lead_submissions(id)
- contact_way_config_id VARCHAR(128) DEFAULT ''
- qr_code_url TEXT DEFAULT ''
- employee_userid VARCHAR(100) DEFAULT ''
- status VARCHAR(20) DEFAULT 'active'
- used_at TIMESTAMPTZ NULL
- created_at TIMESTAMPTZ DEFAULT now()

---

## 3. 表单 schema 建议

最小字段定义：

```json
{
  "fields": [
    {
      "key": "nickname",
      "label": "昵称",
      "type": "text",
      "required": true,
      "placeholder": "请输入你的称呼",
      "profile_field": "nickname",
      "tag_enabled": false,
      "sort": 10
    },
    {
      "key": "role_self",
      "label": "属性",
      "type": "select",
      "required": true,
      "options": [
        {"label": "1", "value": "1"},
        {"label": "0.5", "value": "0.5"},
        {"label": "0", "value": "0"},
        {"label": "side", "value": "side"}
      ],
      "profile_field": "role_self",
      "sort": 60
    }
  ]
}
```

字段类型第一期只做：text / number / select / radio / textarea / checkbox。
图片上传暂时可复用当前 member photo 逻辑，放 Phase 2.5 或 Phase 4 后再补。

---

## 4. 第一阶段详细任务：后台可配置表单

### Task 1: 新增 lead_forms 和 lead_form_versions 模型

Files:
- Create: app/models/lead_form.py
- Modify: app/models/__init__.py

Verification:
- python3 -m py_compile app/models/lead_form.py app/models/__init__.py
- 服务 venv 导入：from app.models.lead_form import LeadForm, LeadFormVersion

### Task 2: 新增 Pydantic schemas

Files:
- Create: app/schemas/lead_form.py

Schemas:
- LeadFormFieldOption
- LeadFormField
- LeadFormCreate
- LeadFormUpdate
- LeadFormOut
- LeadFormPublishOut

Verification:
- python3 -m py_compile app/schemas/lead_form.py
- 用一个包含 nickname/city/role_self 的 schema 做 Pydantic 校验。

### Task 3: 新增 admin_lead_forms router

Files:
- Create: app/routers/admin_lead_forms.py
- Modify: app/main.py

Endpoints:
- GET /api/admin/lead-forms
- POST /api/admin/lead-forms
- GET /api/admin/lead-forms/{form_id}
- PUT /api/admin/lead-forms/{form_id}
- POST /api/admin/lead-forms/{form_id}/publish
- POST /api/admin/lead-forms/{form_id}/archive
- POST /api/admin/lead-forms/{form_id}/duplicate

Verification:
- python3 -m py_compile app/routers/admin_lead_forms.py app/main.py
- curl -s http://127.0.0.1:8000/api/admin/lead-forms 应返回 401/403 或列表，不能 404。

### Task 4: 初始化默认公开引流表单

Files:
- Create: scripts/init_default_lead_form.py 或在 admin 接口手动创建

Default slug:
- public-wechat-v1

Default fields:
- nickname, city, age, height, weight, role_self, body_type, job, income, lifestyle_status, hobbies, current_situation, expectation, long_distance, phone, wechat_id

Verification:
- 后台 API 能查到 public-wechat-v1。

### Task 5: 后台前端 LeadFormManageView

Files:
- Create: yufeng-admin-web/src/views/LeadFormManageView.vue
- Modify: yufeng-admin-web/src/router/index.js
- Modify: yufeng-admin-web/src/views/DashboardLayout.vue

UI:
- 表单列表
- 新建/编辑抽屉
- 字段列表可新增/删除/排序
- 选项编辑
- 发布/下线
- 预览 JSON 或简单表单预览

Verification:
- cd yufeng-admin-web && npm run build
- 访问 /admin/lead-forms 不白屏。

### Task 6: 部署并 smoke test

Commands:
- cd /home/ubuntu/yufeng-event-api
- python3 -m py_compile app/models/lead_form.py app/schemas/lead_form.py app/routers/admin_lead_forms.py app/main.py
- sudo systemctl restart yufeng-event-api
- systemctl is-active yufeng-event-api
- curl -s -o /dev/null -w '%{http_code}\n' https://yufeng.team/api/admin/lead-forms
- cd yufeng-admin-web && npm run build && rsync dist/ /var/www/yufeng-admin/

Acceptance:
- 后台菜单出现“引流表单”。
- 后端路由不是 404。
- 当前 https://yufeng.team/api/wecom/tag/register-form 仍正常。

---

## 5. 风险与兜底

1. 企微 state 回调字段必须实测。
   - 不能假设字段名。
   - Phase 3 先记录脱敏 payload，再启用自动绑定。

2. 当前项目无 Alembic。
   - 新增表用 create_all 可接受。
   - 修改旧表必须单独 ALTER 并备份。

3. 先新增，不重写。
   - 不要第一步就替换当前 REGISTER_FORM_HTML。
   - 现有专属链接先保持稳定。

4. 标签策略不要膨胀。
   - 当前只打 层级·S/A/B/C 是干净策略。
   - 来源标签可加：来源·个人微信 / 来源·小红书。
   - 城市/收入/体型优先放 description 和后台数据，不一定全部打企微标签。

5. 隐私字段要脱敏。
   - 后台手机号/微信号默认遮罩。
   - 日志不写完整敏感信息。

---

## 6. 下一步执行建议

先做 Phase 1：总后台可配置表单。
原因：
- 无企微副作用。
- 不影响当前专属登记链接。
- 后续公开引流、state 绑定、自动标签都依赖这个基础。

第一批可交付：
- 后台“引流表单”菜单
- lead_forms / lead_form_versions 表
- 表单 CRUD + 发布
- 默认 public-wechat-v1 表单
- 前端可编辑选项和必填
- 不接公开提交、不写企微
