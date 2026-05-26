<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const taskLoading = ref(false)
const usageLoading = ref(false)
const reviewLoading = ref(false)
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const overview = ref({})
const tasks = ref([])
const usage = ref([])
const usageTotal = ref(0)

const taskDialogVisible = ref(false)
const taskSubmitting = ref(false)
const editingTaskId = ref(null)
const taskForm = reactive({
  title: '',
  category: 'wecom',
  source: 'manual',
  owner: '',
  status: 'pending',
  priority: 3,
  detail: '',
  result: '',
})

const review = reactive({
  review_date: selectedDate.value,
  status: 'draft',
  summary: '',
  wins: '',
  risks: '',
  next_actions: '',
  ai_suggestion: '',
  is_locked: false,
})

const statusMap = {
  pending: { label: '待处理', type: 'warning' },
  running: { label: '进行中', type: 'primary' },
  done: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  skipped: { label: '跳过', type: 'info' },
}

const categoryMap = {
  moments: '朋友圈',
  wecom: '企微客服',
  review: '每日复盘',
  scripts: '话术库',
  action: '指令动作',
  general: '通用',
}

const statCards = computed(() => [
  { label: '待处理任务', value: overview.value.pending_tasks || 0, desc: 'pending + running', tone: 'orange' },
  { label: '已完成任务', value: overview.value.done_tasks || 0, desc: '今日 done', tone: 'green' },
  { label: 'AI 调用次数', value: overview.value.ai_usage_count || 0, desc: '今日埋点', tone: 'blue' },
  { label: 'Token / 成本', value: `${overview.value.ai_total_tokens || 0}`, desc: `约 ¥${Number(overview.value.ai_estimated_cost_cny || 0).toFixed(4)}`, tone: 'purple' },
])

function statusLabel(status) {
  return statusMap[status]?.label || status || '-'
}

function statusType(status) {
  return statusMap[status]?.type || 'info'
}

function categoryLabel(category) {
  return categoryMap[category] || category || '-'
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 16)
}

async function loadOverview() {
  const res = await request.get('/ops/overview', { params: { day: selectedDate.value } })
  overview.value = res || {}
}

async function loadTasks() {
  taskLoading.value = true
  try {
    const res = await request.get('/ops/tasks', { params: { day: selectedDate.value } })
    tasks.value = res?.items || []
  } finally {
    taskLoading.value = false
  }
}

async function loadUsage() {
  usageLoading.value = true
  try {
    const res = await request.get('/ops/ai-usage', { params: { day: selectedDate.value, page_size: 12 } })
    usage.value = res?.items || []
    usageTotal.value = res?.total || 0
  } finally {
    usageLoading.value = false
  }
}

async function loadReview() {
  reviewLoading.value = true
  try {
    const res = await request.get('/ops/daily-review', { params: { day: selectedDate.value } })
    Object.assign(review, res || {}, { review_date: selectedDate.value })
  } finally {
    reviewLoading.value = false
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadOverview(), loadTasks(), loadUsage(), loadReview()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载运营台失败')
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  refreshAll()
}

function openCreateTask() {
  editingTaskId.value = null
  Object.assign(taskForm, {
    title: '', category: 'wecom', source: 'manual', owner: '', status: 'pending', priority: 3, detail: '', result: '',
  })
  taskDialogVisible.value = true
}

function openEditTask(row) {
  editingTaskId.value = row.id
  Object.assign(taskForm, {
    title: row.title || '',
    category: row.category || 'general',
    source: row.source || 'manual',
    owner: row.owner || '',
    status: row.status || 'pending',
    priority: row.priority || 3,
    detail: row.detail || '',
    result: row.result || '',
  })
  taskDialogVisible.value = true
}

async function saveTask() {
  if (!taskForm.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  taskSubmitting.value = true
  try {
    const payload = { ...taskForm, task_date: selectedDate.value }
    if (editingTaskId.value) {
      await request.put(`/ops/tasks/${editingTaskId.value}`, payload)
      ElMessage.success('任务已更新')
    } else {
      await request.post('/ops/tasks', payload)
      ElMessage.success('任务已创建')
    }
    taskDialogVisible.value = false
    await Promise.all([loadOverview(), loadTasks()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存任务失败')
  } finally {
    taskSubmitting.value = false
  }
}

async function markTask(row, status) {
  try {
    await request.put(`/ops/tasks/${row.id}`, { status })
    await Promise.all([loadOverview(), loadTasks()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新状态失败')
  }
}

async function saveReview(lock = false) {
  reviewLoading.value = true
  try {
    await request.put('/ops/daily-review', {
      review_date: selectedDate.value,
      status: lock ? 'reviewed' : review.status,
      summary: review.summary,
      wins: review.wins,
      risks: review.risks,
      next_actions: review.next_actions,
      ai_suggestion: review.ai_suggestion,
      is_locked: lock || review.is_locked,
    })
    ElMessage.success(lock ? '复盘已确认锁定' : '复盘已保存')
    await Promise.all([loadOverview(), loadReview()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存复盘失败')
  } finally {
    reviewLoading.value = false
  }
}

onMounted(refreshAll)
</script>

<template>
  <div class="ops-console" v-loading="loading">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">PRIVATE OPS P0</p>
        <h2>客服大脑运营台</h2>
        <p>把今日运营任务、AI 调用成本、每日复盘先统一收口到总后台，后续再扩展话术库、朋友圈确认台和动作中心。</p>
      </div>
      <div class="hero-actions">
        <el-date-picker v-model="selectedDate" type="date" value-format="YYYY-MM-DD" @change="onDateChange" />
        <el-button type="primary" @click="refreshAll">刷新</el-button>
      </div>
    </section>

    <div class="stat-grid">
      <article v-for="card in statCards" :key="card.label" class="stat-card" :class="`tone-${card.tone}`">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <em>{{ card.desc }}</em>
      </article>
    </div>

    <section class="main-grid">
      <el-card shadow="never" class="panel-card task-card">
        <template #header>
          <div class="card-header">
            <div>
              <strong>今日运营任务</strong>
              <p>默认种子任务会自动生成，可补充人工任务。</p>
            </div>
            <el-button type="primary" size="small" @click="openCreateTask">新增任务</el-button>
          </div>
        </template>
        <el-table :data="tasks" v-loading="taskLoading" stripe>
          <el-table-column label="时间" width="120">
            <template #default="{ row }">{{ formatTime(row.scheduled_at) }}</template>
          </el-table-column>
          <el-table-column label="任务" min-width="240">
            <template #default="{ row }">
              <div class="task-title">{{ row.title }}</div>
              <div class="task-detail">{{ row.detail || '-' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="100">
            <template #default="{ row }"><el-tag size="small" type="info">{{ categoryLabel(row.category) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态" width="95">
            <template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text @click="openEditTask(row)">编辑</el-button>
              <el-button v-if="row.status !== 'done'" size="small" text type="success" @click="markTask(row, 'done')">完成</el-button>
              <el-button v-if="row.status !== 'running'" size="small" text type="primary" @click="markTask(row, 'running')">进行</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="panel-card review-card">
        <template #header>
          <div class="card-header">
            <div>
              <strong>每日复盘把关</strong>
              <p>先人工保存，确认后锁定。</p>
            </div>
            <el-tag :type="review.is_locked ? 'success' : 'warning'">{{ review.is_locked ? '已锁定' : '草稿' }}</el-tag>
          </div>
        </template>
        <el-form label-position="top" :disabled="review.is_locked" v-loading="reviewLoading">
          <el-form-item label="今日总结">
            <el-input v-model="review.summary" type="textarea" :rows="3" placeholder="今天客服/朋友圈/会员运营整体情况" />
          </el-form-item>
          <el-form-item label="做得好的地方">
            <el-input v-model="review.wins" type="textarea" :rows="2" placeholder="有效话术、转化亮点、优质客户反馈" />
          </el-form-item>
          <el-form-item label="风险/问题">
            <el-input v-model="review.risks" type="textarea" :rows="2" placeholder="未处理客户、素材问题、成本异常" />
          </el-form-item>
          <el-form-item label="明日动作">
            <el-input v-model="review.next_actions" type="textarea" :rows="2" placeholder="明天要继续推进的动作" />
          </el-form-item>
          <el-form-item label="AI 建议/备注">
            <el-input v-model="review.ai_suggestion" type="textarea" :rows="2" placeholder="后续可接自动总结" />
          </el-form-item>
        </el-form>
        <div class="review-actions">
          <span v-if="review.reviewed_by">确认人：{{ review.reviewed_by }} · {{ formatTime(review.reviewed_at) }}</span>
          <span v-else></span>
          <div>
            <el-button :disabled="review.is_locked" :loading="reviewLoading" @click="saveReview(false)">保存草稿</el-button>
            <el-button type="primary" :disabled="review.is_locked" :loading="reviewLoading" @click="saveReview(true)">确认复盘</el-button>
          </div>
        </div>
      </el-card>
    </section>

    <el-card shadow="never" class="panel-card usage-card">
      <template #header>
        <div class="card-header">
          <div>
            <strong>AI Token / 成本记录</strong>
            <p>当前先接入企微异步 DeepSeek 回复链路；成本为估算，财务以供应商账单为准。</p>
          </div>
          <el-tag>共 {{ usageTotal }} 条</el-tag>
        </div>
      </template>
      <el-table :data="usage" v-loading="usageLoading" stripe>
        <el-table-column label="时间" width="150"><template #default="{ row }">{{ formatTime(row.occurred_at) }}</template></el-table-column>
        <el-table-column prop="source" label="来源" width="140" />
        <el-table-column prop="scene" label="场景" width="120" />
        <el-table-column prop="model" label="模型" width="140" />
        <el-table-column label="Token" width="120"><template #default="{ row }">{{ row.total_tokens || 0 }}</template></el-table-column>
        <el-table-column label="耗时" width="100"><template #default="{ row }">{{ row.latency_ms || 0 }}ms</template></el-table-column>
        <el-table-column label="估算成本" width="110"><template #default="{ row }">¥{{ Number(row.estimated_cost_cny || 0).toFixed(4) }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="request_preview" label="请求预览" min-width="220" show-overflow-tooltip />
        <el-table-column prop="response_preview" label="回复预览" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-dialog v-model="taskDialogVisible" :title="editingTaskId ? '编辑运营任务' : '新增运营任务'" width="560px">
      <el-form :model="taskForm" label-width="90px">
        <el-form-item label="标题" required><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="分类"><el-select v-model="taskForm.category"><el-option v-for="(label, key) in categoryMap" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        <el-form-item label="来源"><el-input v-model="taskForm.source" /></el-form-item>
        <el-form-item label="负责人"><el-input v-model="taskForm.owner" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="taskForm.status"><el-option v-for="(item, key) in statusMap" :key="key" :label="item.label" :value="key" /></el-select></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="taskForm.priority" :min="1" :max="5" /></el-form-item>
        <el-form-item label="详情"><el-input v-model="taskForm.detail" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="结果"><el-input v-model="taskForm.result" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSubmitting" @click="saveTask">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ops-console { display: flex; flex-direction: column; gap: 18px; }
.hero-panel { display: flex; justify-content: space-between; gap: 20px; align-items: center; padding: 24px; border-radius: 22px; color: #fff; background: linear-gradient(135deg, #0f172a, #0f766e); }
.eyebrow { margin: 0 0 8px; color: #99f6e4; font-weight: 800; letter-spacing: .12em; font-size: 12px; }
.hero-panel h2 { margin: 0; font-size: 30px; }
.hero-panel p { margin: 10px 0 0; color: #dbeafe; }
.hero-actions { display: flex; gap: 10px; align-items: center; }
.stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.stat-card { padding: 18px; border-radius: 18px; background: #fff; border: 1px solid #e5e7eb; box-shadow: 0 8px 22px rgba(15,23,42,.05); }
.stat-card span, .stat-card em { display: block; color: #64748b; font-style: normal; }
.stat-card strong { display: block; margin: 8px 0; font-size: 28px; color: #0f172a; }
.tone-orange { border-top: 4px solid #f59e0b; }
.tone-green { border-top: 4px solid #10b981; }
.tone-blue { border-top: 4px solid #3b82f6; }
.tone-purple { border-top: 4px solid #8b5cf6; }
.main-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(360px, .75fr); gap: 16px; align-items: start; }
.panel-card { border-radius: 18px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-header strong { font-size: 16px; color: #0f172a; }
.card-header p { margin: 4px 0 0; color: #64748b; font-size: 13px; }
.task-title { font-weight: 700; color: #111827; }
.task-detail { margin-top: 4px; color: #64748b; font-size: 12px; }
.review-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: #64748b; font-size: 13px; }
@media(max-width: 980px) { .stat-grid, .main-grid { grid-template-columns: 1fr; } .hero-panel { flex-direction: column; align-items: flex-start; } }
@media(max-width: 560px) { .hero-actions { width: 100%; flex-direction: column; align-items: stretch; } .stat-card strong { font-size: 24px; } }
</style>
