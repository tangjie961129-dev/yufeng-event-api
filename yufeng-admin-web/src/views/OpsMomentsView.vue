<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const regenLoading = ref(false)
const saving = ref(false)
const wecomLoading = ref({})
const defaultSender = ref('romanyu')
const status = ref(null)
const config = reactive({
  enabled: true,
  pre_generate_time: '02:00',
  rescue_time: '10:00',
  slots: [],
  rules: {},
  prompts: {},
})
const crontab = ref('')

const summary = computed(() => status.value?.summary || {})
const slots = computed(() => status.value?.slots || [])

function assignConfig(c) {
  config.enabled = c?.enabled ?? true
  config.pre_generate_time = c?.pre_generate_time || '02:00'
  config.rescue_time = c?.rescue_time || '10:00'
  config.slots = JSON.parse(JSON.stringify(c?.slots || []))
  config.rules = JSON.parse(JSON.stringify(c?.rules || {}))
  config.prompts = JSON.parse(JSON.stringify(c?.prompts || {}))
}

async function loadStatus() {
  loading.value = true
  try {
    const [s, c] = await Promise.all([
      request.get('/ops/moments/status'),
      request.get('/ops/moments/config'),
    ])
    status.value = s.status
    assignConfig(c.config)
    crontab.value = c.crontab || ''
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const res = await request.put('/ops/moments/config', { config, apply_cron: true })
    status.value = res.status
    assignConfig(res.config)
    ElMessage.success('配置已保存，定时任务已同步')
  } finally {
    saving.value = false
  }
}

async function regenImages() {
  await ElMessageBox.confirm('确认执行一键补图？只补缺失/失败配图，不会重写文案。', '一键补图', { type: 'warning' })
  regenLoading.value = true
  try {
    const res = await request.post('/ops/moments/regen-images')
    status.value = res.status
    if (res.success) ElMessage.success('补图完成')
    else ElMessage.warning(res.message || '补图执行结束，但可能仍有缺图')
  } finally {
    regenLoading.value = false
  }
}

function imageKb(row) {
  return row.image_size ? `${Math.round(row.image_size / 1024)}KB` : '-'
}

function wecomTaskLabel(row) {
  const task = row.wecom_task
  if (!task) return '未放入'
  const raw = task.wecom_response || {}
  const id = raw.jobid || raw.moment_id || raw.task_id || '已创建'
  return `${id}`
}

async function pushToWecom(row) {
  if (!row.text_ok || !row.image_ok) {
    ElMessage.warning('文案或配图未就绪，不能放入企微待发表')
    return
  }
  await ElMessageBox.confirm(`确认把「${row.label || row.slot}」放入企微客户朋友圈待发表？\n负责发表员工：${defaultSender.value}`, '放入企微待发表', { type: 'warning' })
  wecomLoading.value[row.slot] = true
  try {
    const res = await request.post('/ops/moments/wecom-task', {
      slot: row.slot,
      sender_users: [defaultSender.value],
      include_image: true,
      dry_run: false,
    })
    status.value = res.status
    ElMessage.success('已创建企微客户朋友圈待发表任务')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建企微待发表任务失败')
  } finally {
    wecomLoading.value[row.slot] = false
  }
}

function addSlot() {
  const all = ['11:00', '17:00', '18:00', '20:00']
  const used = new Set(config.slots.map(s => s.key))
  const key = all.find(x => !used.has(x))
  if (!key) return ElMessage.warning('当前脚本只支持4个固定内容位，可通过启用/停用控制条数')
  config.slots.push({ key, send_time: key, enabled: true, type: 'member', label: '新时段', image_file: '' })
}

onMounted(loadStatus)
</script>

<template>
  <div class="ops-page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Moments Console</p>
        <h1>朋友圈推送台</h1>
        <p>不仅看今日状态，也可以直接修改提示词、时间、条数和公开规则，并把内容直接放入企微客户朋友圈待发表。</p>
      </div>
      <div class="head-actions">
        <el-button :loading="loading" @click="loadStatus">刷新</el-button>
        <el-button type="success" :loading="saving" @click="saveConfig">保存配置</el-button>
        <el-button type="primary" :loading="regenLoading" @click="regenImages">一键补图</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="12" :md="6"><el-card shadow="never" class="metric"><strong>{{ summary.text_ok || 0 }}/{{ summary.total || 4 }}</strong><span>文案就绪</span></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card shadow="never" class="metric"><strong>{{ summary.image_ok || 0 }}/{{ summary.total || 4 }}</strong><span>配图就绪</span></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card shadow="never" class="metric"><strong>{{ summary.ready ? 'READY' : '待处理' }}</strong><span>今日状态</span></el-card></el-col>
      <el-col :xs="12" :md="6"><el-card shadow="never" class="metric"><strong>{{ status?.date || '-' }}</strong><span>日期</span></el-card></el-col>
    </el-row>

    <el-tabs type="border-card">
      <el-tab-pane label="今日状态">
        <el-alert v-if="summary.missing_images?.length" type="warning" show-icon :closable="false" :title="`缺图：${summary.missing_images.join('、')}。建议点击一键补图。`" />
        <el-alert v-else-if="summary.ready" type="success" show-icon :closable="false" title="今日文案和配图已全部就绪。" />
        <el-table :data="slots" v-loading="loading" border style="margin-top: 12px">
          <el-table-column prop="slot" label="内容位" width="90" />
          <el-table-column prop="send_time" label="发送时间" width="100" />
          <el-table-column label="类型/会员" width="170"><template #default="{ row }"><strong>{{ row.label || row.type || '-' }}</strong><br><span class="muted">{{ row.user || '-' }}</span></template></el-table-column>
          <el-table-column label="文案" min-width="300"><template #default="{ row }"><el-tag :type="row.text_ok ? 'success' : 'danger'">{{ row.text_ok ? '已生成' : '缺文案' }}</el-tag><p class="preview">{{ row.text_preview || '暂无文案' }}</p></template></el-table-column>
          <el-table-column label="配图" min-width="220"><template #default="{ row }"><el-tag :type="row.image_ok ? 'success' : 'danger'">{{ row.image_ok ? '已就绪' : '缺图/失败' }}</el-tag><div class="path">{{ row.image || '-' }}</div><div class="muted">{{ imageKb(row) }}</div></template></el-table-column>
          <el-table-column label="企微待发表" width="210" fixed="right">
            <template #default="{ row }">
              <el-tag :type="row.wecom_task ? 'success' : 'info'">{{ row.wecom_task ? '已放入' : '未放入' }}</el-tag>
              <div class="muted task-id">{{ wecomTaskLabel(row) }}</div>
              <el-button size="small" type="primary" :disabled="!row.text_ok || !row.image_ok" :loading="wecomLoading[row.slot]" @click="pushToWecom(row)">放入待发表</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="时间/条数">
        <el-card shadow="never">
          <template #header>基础定时</template>
          <el-form label-width="130px">
            <el-form-item label="凌晨预生成"><el-input v-model="config.pre_generate_time" placeholder="02:00" /></el-form-item>
            <el-form-item label="补救检查"><el-input v-model="config.rescue_time" placeholder="10:00" /></el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" style="margin-top:12px">
          <template #header><div class="card-head"><span>推送时段（用启用/停用控制每天条数）</span><el-button size="small" @click="addSlot">补回固定内容位</el-button></div></template>
          <el-table :data="config.slots" border>
            <el-table-column label="启用" width="80"><template #default="{ row }"><el-switch v-model="row.enabled" /></template></el-table-column>
            <el-table-column prop="key" label="内容位" width="90" />
            <el-table-column label="发送时间" width="140"><template #default="{ row }"><el-input v-model="row.send_time" placeholder="11:00" /></template></el-table-column>
            <el-table-column label="类型" width="150"><template #default="{ row }"><el-select v-model="row.type"><el-option label="会员推荐" value="member"/><el-option label="配对案例" value="match"/><el-option label="Tips" value="tip"/></el-select></template></el-table-column>
            <el-table-column label="显示名称" min-width="180"><template #default="{ row }"><el-input v-model="row.label" /></template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="提示词">
        <el-form label-position="top">
          <el-form-item label="DeepSeek 系统提示词"><el-input v-model="config.prompts.deepseek_system" type="textarea" :rows="5" /></el-form-item>
          <el-form-item label="会员点评提示词"><el-input v-model="config.prompts.member_comment_instruction" type="textarea" :rows="6" /></el-form-item>
          <el-form-item label="会员配图提示词后缀"><el-input v-model="config.prompts.member_image_suffix" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="配对案例规则"><el-input v-model="config.prompts.match_copy_rule" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="Tips 规则"><el-input v-model="config.prompts.tip_copy_rule" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="发送前净化/拦截说明"><el-input v-model="config.prompts.assistant_sanitize_note" type="textarea" :rows="3" /></el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="规则">
        <el-form label-position="top">
          <el-form-item label="公开文案总规则"><el-input v-model="config.rules.public_style" type="textarea" :rows="5" /></el-form-item>
          <el-form-item label="话题标签"><el-input v-model="config.rules.hashtags" /></el-form-item>
          <el-form-item label="最小图片大小 bytes"><el-input-number v-model="config.rules.min_image_bytes" :min="10000" :step="5000" /></el-form-item>
          <el-form-item label="公开禁用词（逗号分隔，保存为数组）">
            <el-input :model-value="(config.rules.banned_public_words || []).join(',')" @update:model-value="v => config.rules.banned_public_words = v.split(',').map(x => x.trim()).filter(Boolean)" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="cron日志">
        <pre class="log-box">{{ (status?.cron_logs || []).join('\n') || '暂无日志' }}</pre>
        <h3>当前 crontab</h3>
        <pre class="log-box light">{{ crontab || '暂无' }}</pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.ops-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.page-head h1 { margin: 4px 0 8px; font-size: 28px; }
.page-head p { margin: 0; color: #64748b; }
.eyebrow { color: #0f766e !important; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.metric :deep(.el-card__body) { display: flex; flex-direction: column; gap: 6px; }
.metric strong { font-size: 26px; color: #0f172a; }
.metric span, .muted { color: #64748b; font-size: 13px; }
.preview { margin: 8px 0 0; color: #334155; line-height: 1.5; }
.path { margin-top: 8px; color: #475569; font-size: 12px; word-break: break-all; }
.log-box { background: #0f172a; color: #d1fae5; padding: 14px; border-radius: 12px; white-space: pre-wrap; max-height: 360px; overflow: auto; }
.log-box.light { background: #f8fafc; color: #334155; border: 1px solid #e2e8f0; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
@media (max-width: 767px) { .page-head { flex-direction: column; } }
</style>
