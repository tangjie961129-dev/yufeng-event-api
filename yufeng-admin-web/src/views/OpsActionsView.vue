<script setup>
import { onMounted, ref } from 'vue'
import request from '../utils/request'

const loading = ref(false)
const data = ref(null)
const dbSummary = ref([])

async function loadAll() {
  loading.value = true
  try {
    const [a, d] = await Promise.all([
      request.get('/ops/actions'),
      request.get('/ops/db-summary'),
    ])
    data.value = a
    dbSummary.value = d.items || []
  } finally {
    loading.value = false
  }
}

function portType(p) { return p.listening ? 'success' : 'danger' }
function serviceType(s) { return s.status === 'active' ? 'success' : 'danger' }

onMounted(loadAll)
</script>

<template>
  <div class="ops-page" v-loading="loading">
    <div class="page-head">
      <div>
        <p class="eyebrow">Command Center</p>
        <h1>指令动作中心</h1>
        <p>集中查看企微自建应用菜单、自助指令、系统端口、数据源规模和最近助手日志。</p>
      </div>
      <el-button type="primary" @click="loadAll">刷新</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="panel">
          <template #header>运行状态</template>
          <div class="status-line" v-for="s in data?.system?.services || []" :key="s.name">
            <span>{{ s.name }}</span><el-tag :type="serviceType(s)">{{ s.status }}</el-tag>
          </div>
          <div class="status-line" v-for="p in data?.system?.ports || []" :key="p.port">
            <span>{{ p.name }} :{{ p.port }}</span><el-tag :type="portType(p)">{{ p.listening ? 'listening' : 'down' }}</el-tag>
          </div>
          <el-divider />
          <div class="daily-mini">
            <strong>朋友圈今日</strong>
            <span>文案 {{ data?.system?.daily?.text_ok || 0 }}/4</span>
            <span>配图 {{ data?.system?.daily?.image_ok || 0 }}/4</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="panel">
          <template #header>客服大脑数据</template>
          <div class="metric-row"><span>话术规则</span><strong>{{ data?.counts?.playbooks || 0 }}</strong></div>
          <div class="metric-row"><span>助手日志</span><strong>{{ data?.counts?.assistant_logs || 0 }}</strong></div>
          <div class="metric-row"><span>反馈记录</span><strong>{{ data?.counts?.feedback_logs || 0 }}</strong></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="panel">
          <template #header>数据库数据源</template>
          <div class="status-line" v-for="r in dbSummary" :key="r.table">
            <span>{{ r.table }}</span><el-tag :type="r.ok ? 'success' : 'danger'">{{ r.ok ? r.count : '异常' }}</el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>企微菜单 / 自然语言动作</template>
      <el-table :data="data?.menu_actions || []" border>
        <el-table-column prop="group" label="分组" width="100" />
        <el-table-column prop="label" label="功能" width="150" />
        <el-table-column prop="key" label="EventKey" width="220" />
        <el-table-column prop="desc" label="说明" min-width="260" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>最近执行记录</template>
      <el-timeline>
        <el-timeline-item v-for="log in data?.recent_logs || []" :key="log.id" :timestamp="log.created_at">
          <div class="log-title">#{{ log.id }} {{ log.detected_intent || 'general' }} · {{ log.customer_name || log.employee_userid }}</div>
          <div class="log-msg">{{ log.raw_message }}</div>
          <div class="log-reply">{{ log.ai_reply }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<style scoped>
.ops-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.page-head h1 { margin: 4px 0 8px; font-size: 28px; }
.page-head p { margin: 0; color: #64748b; }
.eyebrow { color: #0f766e !important; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.panel { min-height: 260px; }
.status-line, .metric-row { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid #f1f5f9; }
.metric-row strong { font-size: 24px; color: #0f766e; }
.daily-mini { display: flex; gap: 12px; flex-wrap: wrap; color: #475569; }
.log-title { font-weight: 800; color: #0f172a; }
.log-msg { margin: 4px 0; color: #334155; }
.log-reply { color: #64748b; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
@media (max-width: 767px) { .page-head { flex-direction: column; } }
</style>
