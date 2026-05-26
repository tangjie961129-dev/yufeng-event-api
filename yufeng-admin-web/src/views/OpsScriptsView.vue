<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const saving = ref(false)
const q = ref('')
const scenario = ref('')
const items = ref([])
const scenarios = ref([])
const logs = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({
  scenario: 'general',
  trigger_keywords: '',
  recommended_reply: '',
  avoid_words: '',
  style_notes: '',
  source: 'manual',
})

async function loadPlaybooks() {
  loading.value = true
  try {
    const res = await request.get('/ops/playbooks', { params: { q: q.value, scenario: scenario.value, limit: 120 } })
    items.value = res.items || []
    scenarios.value = res.scenarios || []
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  const res = await request.get('/ops/assistant-logs', { params: { limit: 30 } })
  logs.value = res.items || []
}

function openCreate() {
  editingId.value = null
  form.value = { scenario: 'general', trigger_keywords: '', recommended_reply: '', avoid_words: '', style_notes: '', source: 'manual' }
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = { ...row }
  dialogVisible.value = true
}

async function savePlaybook() {
  if (!form.value.recommended_reply.trim()) {
    ElMessage.warning('请填写推荐话术')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await request.patch(`/ops/playbooks/${editingId.value}`, form.value)
      ElMessage.success('已更新话术')
    } else {
      await request.post('/ops/playbooks', form.value)
      ElMessage.success('已新增话术')
    }
    dialogVisible.value = false
    await loadPlaybooks()
  } finally {
    saving.value = false
  }
}

async function removePlaybook(row) {
  await ElMessageBox.confirm(`确认删除「${row.scenario}」这条话术？`, '删除确认', { type: 'warning' })
  await request.delete(`/ops/playbooks/${row.id}`)
  ElMessage.success('已删除')
  await loadPlaybooks()
}

async function seedDefaults() {
  const res = await request.post('/ops/actions/seed-default-playbooks')
  ElMessage.success(`已补默认话术 ${res.created || 0} 条`)
  await loadPlaybooks()
}

onMounted(async () => {
  await Promise.all([loadPlaybooks(), loadLogs()])
})
</script>

<template>
  <div class="ops-page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Customer Brain</p>
        <h1>客服话术库</h1>
        <p>沉淀企微回复助手的场景话术、禁用表达和风格规则，供小助理 RAG 与员工反馈学习使用。</p>
      </div>
      <div class="head-actions">
        <el-button @click="seedDefaults">补默认规则</el-button>
        <el-button type="primary" @click="openCreate">新增话术</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-input v-model="q" placeholder="搜关键词 / 话术 / 风格" clearable @keyup.enter="loadPlaybooks" />
      <el-select v-model="scenario" placeholder="全部场景" clearable>
        <el-option v-for="s in scenarios" :key="s" :label="s" :value="s" />
      </el-select>
      <el-button type="primary" @click="loadPlaybooks">查询</el-button>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>话术规则</template>
          <el-table :data="items" v-loading="loading" row-key="id" border>
            <el-table-column prop="scenario" label="场景" width="120" />
            <el-table-column label="触发关键词" min-width="150">
              <template #default="{ row }"><el-tag v-for="k in row.trigger_keywords.split(/[,，]/).filter(Boolean).slice(0,4)" :key="k" class="tag">{{ k }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="recommended_reply" label="推荐话术" min-width="260" show-overflow-tooltip />
            <el-table-column prop="avoid_words" label="避坑" min-width="120" show-overflow-tooltip />
            <el-table-column label="效果" width="105">
              <template #default="{ row }">{{ row.success_count }}/{{ row.usage_count }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removePlaybook(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="log-card">
          <template #header>最近助手对话</template>
          <div v-for="log in logs" :key="log.id" class="log-item">
            <div class="log-meta">#{{ log.id }} {{ log.detected_intent || 'general' }} · {{ log.employee_userid }}</div>
            <div class="log-msg">{{ log.raw_message }}</div>
            <div class="log-reply">{{ log.ai_reply }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑话术' : '新增话术'" width="720px">
      <el-form label-width="92px">
        <el-form-item label="场景"><el-input v-model="form.scenario" /></el-form-item>
        <el-form-item label="触发词"><el-input v-model="form.trigger_keywords" placeholder="逗号分隔，例如：怎么回,客户问,话术" /></el-form-item>
        <el-form-item label="推荐话术"><el-input v-model="form.recommended_reply" type="textarea" :rows="6" /></el-form-item>
        <el-form-item label="禁用表达"><el-input v-model="form.avoid_words" /></el-form-item>
        <el-form-item label="风格说明"><el-input v-model="form.style_notes" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="来源"><el-input v-model="form.source" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePlaybook">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ops-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.page-head h1 { margin: 4px 0 8px; font-size: 28px; }
.page-head p { margin: 0; color: #64748b; }
.eyebrow { color: #0f766e !important; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.head-actions { display: flex; gap: 8px; }
.filter-card :deep(.el-card__body) { display: flex; gap: 10px; }
.filter-card .el-input { max-width: 360px; }
.filter-card .el-select { width: 180px; }
.tag { margin: 2px 4px 2px 0; }
.log-card { max-height: 720px; overflow: auto; }
.log-item { padding: 10px 0; border-bottom: 1px solid #e5e7eb; }
.log-meta { color: #94a3b8; font-size: 12px; }
.log-msg { color: #0f172a; font-weight: 700; margin: 4px 0; }
.log-reply { color: #64748b; font-size: 13px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
@media (max-width: 767px) { .page-head, .filter-card :deep(.el-card__body) { flex-direction: column; } .head-actions { width: 100%; } }
</style>
