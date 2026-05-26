<script setup>
const healthCards = [
  { label: '企微回调', value: '在线', tone: 'green', desc: '自建应用 5 秒内先响应，复杂任务走 Hermes 异步' },
  { label: '客服大脑', value: '已接入', tone: 'blue', desc: 'DeepSeek + Hermes Gateway + GBrain 知识库' },
  { label: '会员主库', value: '可查询', tone: 'purple', desc: '回复助手可访问 users 表与会员档案摘要' },
  { label: '朋友圈任务', value: '运行中', tone: 'orange', desc: '早中晚会员推荐 + 彩虹交友 tips 预生成/推送' },
]

const brainModules = [
  {
    title: '企微自建应用助手',
    status: '已上线',
    text: '员工把客户问题转发/粘贴给自建应用，系统返回处理思路 + 可直接发给客户的话术。',
    actions: ['秒回占位', '异步生成', '员工侧可复制'],
  },
  {
    title: 'Hermes + GBrain 客服大脑',
    status: '已接入',
    text: '结合屿风知识库、运营规则、历史话术和会员数据库，为员工提供更像真人运营的回复。',
    actions: ['知识库检索', '数据库上下文', '话术沉淀'],
  },
  {
    title: '会员档案/标签动作',
    status: '建设中',
    text: '围绕查档案、发专属链接、打层级标签、回补备注、匹配推荐等动作做成可审计操作台。',
    actions: ['查档案', '发链接', '打标签', '匹配推荐'],
  },
  {
    title: '朋友圈推送操作台',
    status: '待接 UI',
    text: '把每日文案、配图、缺图补救、确认发送、失败状态统一放到总后台，和小程序业务后台分开。',
    actions: ['预览', '微调', '补图', '确认发送'],
  },
]

const todayTasks = [
  { time: '02:00', title: '预生成今日朋友圈', state: '自动任务', detail: '3 条会员推荐 + 1 条交友 tips' },
  { time: '10:00', title: '缺图补救检查', state: '自动任务', detail: '只补缺失配图，不重跑文案' },
  { time: '10:55 / 16:55 / 17:55 / 19:55', title: '朋友圈推送窗口', state: '待接入确认台', detail: '后续在这里做预览、微调、确认发送' },
  { time: '全天', title: '企微客户回复辅助', state: '在线', detail: '员工转发客户问题给小助理获取回复草稿' },
]

const quickLinks = [
  { label: '企微历史会员回补', path: '/wecom-backfill', desc: '客户运营工具，归属总后台' },
  { label: '会员标签管理', path: '/member-tags', desc: '层级/标签运营工具，归属总后台' },
  { label: '小程序业务后台入口', path: '/miniapp-dashboard', desc: '活动、订单、页面装修等业务管理保持独立' },
]
</script>

<template>
  <div class="private-ops-page">
    <section class="ops-hero">
      <div>
        <p class="eyebrow">YUFENG PRIVATE OPS CENTER</p>
        <h1>总后台管理 · 私域客服大脑</h1>
        <p class="hero-desc">
          这里专门管理企微助手、Hermes/GBrain 客服大脑、话术反馈闭环、会员运营动作和朋友圈推送状态。
          小程序活动/订单/页面装修等业务后台已拆到“⼩程序业务后台”分组，不再混在总后台首屏。
        </p>
      </div>
      <div class="hero-badge">
        <strong>当前阶段</strong>
        <span>客服大脑操作台骨架</span>
      </div>
    </section>

    <div class="ops-grid health-grid">
      <div v-for="card in healthCards" :key="card.label" class="ops-card" :class="`tone-${card.tone}`">
        <div class="card-label">{{ card.label }}</div>
        <div class="card-value">{{ card.value }}</div>
        <p>{{ card.desc }}</p>
      </div>
    </div>

    <section class="section-block">
      <div class="section-title">
        <div>
          <h2>客服大脑模块</h2>
          <p>这部分只服务私域/企微运营，不放进小程序业务管理。</p>
        </div>
      </div>
      <div class="module-grid">
        <article v-for="item in brainModules" :key="item.title" class="module-card">
          <div class="module-head">
            <h3>{{ item.title }}</h3>
            <el-tag size="small" effect="dark">{{ item.status }}</el-tag>
          </div>
          <p>{{ item.text }}</p>
          <div class="tag-row">
            <el-tag v-for="action in item.actions" :key="action" size="small" type="info">{{ action }}</el-tag>
          </div>
        </article>
      </div>
    </section>

    <section class="section-block split-block">
      <el-card class="page-card" shadow="never">
        <template #header>
          <strong>今日运营任务</strong>
        </template>
        <div class="timeline-list">
          <div v-for="task in todayTasks" :key="task.title" class="timeline-item">
            <div class="task-time">{{ task.time }}</div>
            <div class="task-body">
              <div class="task-title">{{ task.title }} <el-tag size="small">{{ task.state }}</el-tag></div>
              <p>{{ task.detail }}</p>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="page-card" shadow="never">
        <template #header>
          <strong>后台边界</strong>
        </template>
        <el-alert
          title="总后台 ≠ 小程序管理后台"
          description="总后台管客服大脑、企微助手、朋友圈推送、话术库、标签/客户运营；小程序后台管会员、活动、订单、课程、页面装修、分销等业务数据。"
          type="warning"
          show-icon
          :closable="false"
        />
        <div class="quick-links">
          <router-link v-for="link in quickLinks" :key="link.path" :to="link.path" class="quick-link">
            <strong>{{ link.label }}</strong>
            <span>{{ link.desc }}</span>
          </router-link>
        </div>
      </el-card>
    </section>
  </div>
</template>

<style scoped>
.private-ops-page { display: flex; flex-direction: column; gap: 20px; }
.ops-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  border-radius: 24px;
  color: #fff;
  background: radial-gradient(circle at top left, rgba(45, 212, 191, .28), transparent 35%), linear-gradient(135deg, #0f172a, #1e293b 55%, #0f766e);
  box-shadow: 0 18px 45px rgba(15, 23, 42, .18);
}
.eyebrow { margin: 0 0 10px; color: #99f6e4; font-weight: 800; letter-spacing: .12em; font-size: 12px; }
.ops-hero h1 { margin: 0; font-size: 34px; line-height: 1.2; }
.hero-desc { max-width: 840px; margin: 14px 0 0; color: #dbeafe; font-size: 15px; }
.hero-badge { align-self: flex-start; min-width: 180px; padding: 16px; border-radius: 18px; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.22); }
.hero-badge strong, .hero-badge span { display: block; }
.hero-badge span { margin-top: 8px; color: #ccfbf1; }
.ops-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.ops-card { padding: 18px; border-radius: 20px; background: #fff; border: 1px solid #e5e7eb; box-shadow: 0 10px 26px rgba(15, 23, 42, .06); }
.card-label { color: #64748b; font-size: 13px; }
.card-value { margin-top: 8px; font-size: 28px; font-weight: 800; color: #0f172a; }
.ops-card p { margin: 8px 0 0; color: #64748b; font-size: 13px; }
.tone-green { border-top: 4px solid #10b981; }
.tone-blue { border-top: 4px solid #3b82f6; }
.tone-purple { border-top: 4px solid #8b5cf6; }
.tone-orange { border-top: 4px solid #f59e0b; }
.section-block { display: flex; flex-direction: column; gap: 14px; }
.section-title h2 { margin: 0; color: #0f172a; }
.section-title p { margin: 4px 0 0; color: #64748b; }
.module-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.module-card { padding: 20px; border-radius: 20px; background: #fff; border: 1px solid #e5e7eb; }
.module-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.module-head h3 { margin: 0; color: #111827; }
.module-card p { color: #64748b; }
.tag-row { display: flex; gap: 8px; flex-wrap: wrap; }
.split-block { display: grid; grid-template-columns: 1.2fr .8fr; gap: 16px; }
.timeline-list { display: flex; flex-direction: column; gap: 14px; }
.timeline-item { display: flex; gap: 14px; padding-bottom: 14px; border-bottom: 1px solid #eef2f7; }
.timeline-item:last-child { border-bottom: 0; padding-bottom: 0; }
.task-time { width: 120px; color: #0f766e; font-weight: 800; }
.task-title { color: #111827; font-weight: 700; }
.task-body p { margin: 6px 0 0; color: #64748b; }
.quick-links { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.quick-link { display: flex; flex-direction: column; gap: 4px; padding: 14px; border-radius: 14px; border: 1px solid #e5e7eb; color: #111827; text-decoration: none; background: #f8fafc; }
.quick-link span { color: #64748b; font-size: 13px; }
@media(max-width: 900px) {
  .ops-hero, .split-block { grid-template-columns: 1fr; display: grid; }
  .ops-grid, .module-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media(max-width: 560px) {
  .ops-grid, .module-grid { grid-template-columns: 1fr; }
  .ops-hero { padding: 20px; }
  .ops-hero h1 { font-size: 26px; }
  .task-time { width: 82px; font-size: 12px; }
}
</style>
