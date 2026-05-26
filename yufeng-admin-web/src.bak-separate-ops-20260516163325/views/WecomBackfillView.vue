<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const applyingId = ref(null)
const logsLoading = ref(false)
const keyword = ref('')
const employeeUserid = ref('TangZengRong')
const candidates = ref([])
const logs = ref([])
const lastQuery = ref('')

const employeeOptions = [
  { label: 'TangZengRong', value: 'TangZengRong' },
  { label: 'TangJieSiRenHao', value: 'TangJieSiRenHao' },
  { label: 'romanyu', value: 'romanyu' },
]

function confidenceType(confidence) {
  if (confidence === 'high') return 'success'
  if (confidence === 'medium') return 'warning'
  if (confidence === 'manual') return 'primary'
  if (confidence === 'low') return 'info'
  return 'danger'
}

async function preview() {
  if (!keyword.value.trim()) {
    ElMessage.warning('请输入昵称 / 微信号 / 手机号尾号')
    return
  }
  loading.value = true
  try {
    const res = await request.post('/wecom-backfill/preview', {
      keyword: keyword.value.trim(),
      employee_userid: employeeUserid.value,
      limit: 20,
    })
    candidates.value = res.candidates || []
    lastQuery.value = keyword.value.trim()
    if (!candidates.value.length) {
      ElMessage.info('没有查到候选会员')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

async function applyCandidate(row, action) {
  const actionLabel = {
    apply_remark: '只补企微备注/描述',
    apply_tags: '只补层级标签',
    apply_all: '同步备注/描述 + 标签',
  }[action]
  const profile = row.profile || {}
  const match = row.wecom_match || {}
  let externalUserid = match.external_userid || ''

  if (!externalUserid) {
    try {
      const { value } = await ElMessageBox.prompt(
        '系统没有自动匹配到企微客户。请手动填写 external_userid 后再同步；如果暂时没有，可取消。',
        `人工指定企微客户：${profile.nickname || row.old_user_id}`,
        {
          confirmButtonText: '继续同步',
          cancelButtonText: '取消',
          inputPlaceholder: 'wmxxxxxxxx',
          inputPattern: /^\S{6,}$/,
          inputErrorMessage: '请输入有效 external_userid',
        }
      )
      externalUserid = value
    } catch {
      return
    }
  }

  try {
    await ElMessageBox.confirm(
      `确认对「${profile.nickname || row.old_user_id}」执行：${actionLabel}？\n\n备注：${profile.remark || '无'}\n标签：${(profile.tags || []).join('、') || '无'}`,
      '确认写入企微',
      { confirmButtonText: '确认写入', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  applyingId.value = `${row.old_user_id}-${action}`
  try {
    const res = await request.post('/wecom-backfill/apply', {
      old_user_id: row.old_user_id,
      employee_userid: employeeUserid.value,
      external_userid: externalUserid,
      action,
    })
    ElMessage.success('同步完成')
    await loadLogs()
    if (res.message) {
      ElMessageBox.alert(res.message, '同步结果', { confirmButtonText: '知道了' })
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '同步失败')
  } finally {
    applyingId.value = null
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const res = await request.get('/wecom-backfill/logs', { params: { limit: 30 } })
    logs.value = res.items || []
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '日志加载失败')
  } finally {
    logsLoading.value = false
  }
}

loadLogs()
</script>

<template>
  <div class="backfill-page">
    <el-card class="page-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <h2>企微历史会员回补</h2>
            <p>从老登记库生成候选资料，先预览，再确认写入企微备注/标签。</p>
          </div>
          <el-button @click="loadLogs" :loading="logsLoading">刷新日志</el-button>
        </div>
      </template>

      <el-alert
        title="安全规则：预览不会改企微；只有点击同步按钮并二次确认后才会写企微。自动匹配不到客户时，需要人工填写 external_userid。"
        type="info"
        show-icon
        :closable="false"
        class="mb16"
      />

      <div class="search-bar">
        <el-input
          v-model="keyword"
          placeholder="输入昵称 / 微信号 / 手机号尾号，例如：蚂蚁、生木、0258"
          clearable
          @keyup.enter="preview"
        />
        <el-select v-model="employeeUserid" placeholder="选择员工" style="width: 220px">
          <el-option v-for="item in employeeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="preview">生成候选预览</el-button>
      </div>
    </el-card>

    <el-card v-if="lastQuery" class="page-card" shadow="never">
      <template #header>
        <div class="card-header compact">
          <strong>候选结果：{{ lastQuery }}</strong>
          <span class="muted">{{ candidates.length }} 条</span>
        </div>
      </template>

      <el-empty v-if="!candidates.length" description="暂无候选" />
      <div v-else class="candidate-list">
        <el-card v-for="row in candidates" :key="row.old_user_id" class="candidate-card" shadow="hover">
          <div class="candidate-top">
            <div>
              <div class="member-title">
                {{ row.profile?.nickname || '未命名' }}
                <el-tag size="small" type="info">ID {{ row.old_user_id }}</el-tag>
                <el-tag size="small" :type="row.profile?.level === 'S' ? 'danger' : row.profile?.level === 'A' ? 'warning' : 'info'">
                  层级 {{ row.profile?.level || '-' }}
                </el-tag>
              </div>
              <div class="member-sub">
                {{ row.profile?.city || '未知城市' }}｜{{ row.profile?.age || '未知年龄' }}岁｜{{ row.profile?.height || '?' }}/{{ row.profile?.weight || '?' }}｜{{ row.profile?.role_self || '属性未知' }}｜{{ row.profile?.body_type || '体型未知' }}
              </div>
            </div>
            <div class="actions">
              <el-button size="small" @click="applyCandidate(row, 'apply_remark')" :loading="applyingId === `${row.old_user_id}-apply_remark`">只补备注</el-button>
              <el-button size="small" @click="applyCandidate(row, 'apply_tags')" :loading="applyingId === `${row.old_user_id}-apply_tags`">只补标签</el-button>
              <el-button size="small" type="primary" @click="applyCandidate(row, 'apply_all')" :loading="applyingId === `${row.old_user_id}-apply_all`">全部同步</el-button>
            </div>
          </div>

          <el-descriptions :column="2" border size="small" class="mt12">
            <el-descriptions-item label="微信">{{ row.profile?.wechat_id_masked || '无' }}</el-descriptions-item>
            <el-descriptions-item label="手机">{{ row.profile?.phone_masked || '无' }}</el-descriptions-item>
            <el-descriptions-item label="职业">{{ row.profile?.job || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="收入">{{ row.profile?.income || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="异地">{{ row.profile?.long_distance || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="标签">{{ (row.profile?.tags || []).join('、') || '无' }}</el-descriptions-item>
            <el-descriptions-item label="建议备注" :span="2">{{ row.profile?.remark || '无' }}</el-descriptions-item>
            <el-descriptions-item label="建议描述" :span="2">{{ row.profile?.description || '无' }}</el-descriptions-item>
            <el-descriptions-item label="期待/状态" :span="2">{{ row.profile?.expectation || row.profile?.current_situation || '无' }}</el-descriptions-item>
          </el-descriptions>

          <div class="match-box">
            <span class="match-label">企微匹配：</span>
            <template v-if="row.wecom_match?.external_userid">
              <el-tag :type="confidenceType(row.wecom_match.confidence)">{{ row.wecom_match.confidence }}</el-tag>
              <span>{{ row.wecom_match.name || '未命名客户' }}</span>
              <span class="muted">{{ row.wecom_match.match_method }}</span>
              <code>{{ row.wecom_match.external_userid }}</code>
            </template>
            <template v-else>
              <el-tag type="danger">未命中</el-tag>
              <span class="muted">{{ row.wecom_match?.error || '当前员工企微客户列表未匹配到' }}</span>
            </template>
          </div>
        </el-card>
      </div>
    </el-card>

    <el-card class="page-card" shadow="never">
      <template #header>
        <div class="card-header compact">
          <strong>最近回补日志</strong>
          <span class="muted">{{ logs.length }} 条</span>
        </div>
      </template>
      <el-table :data="logs" v-loading="logsLoading" size="small" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="会员ID" width="100" />
        <el-table-column prop="employee_userid" label="员工" width="150" />
        <el-table-column prop="confidence" label="置信度" width="100" />
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column label="备注" width="90">
          <template #default="{ row }">
            <el-tag :type="row.remark_applied ? 'success' : 'info'">{{ row.remark_applied ? '已写' : '未写' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tags_applied" label="标签" min-width="180" show-overflow-tooltip />
        <el-table-column prop="error" label="错误" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="190" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.backfill-page { display: flex; flex-direction: column; gap: 16px; }
.page-card { border-radius: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-header h2 { margin: 0 0 6px; font-size: 22px; }
.card-header p { margin: 0; color: #64748b; }
.card-header.compact { min-height: 24px; }
.mb16 { margin-bottom: 16px; }
.mt12 { margin-top: 12px; }
.muted { color: #64748b; font-size: 13px; }
.search-bar { display: flex; gap: 12px; align-items: center; }
.candidate-list { display: flex; flex-direction: column; gap: 14px; }
.candidate-card { border-radius: 14px; }
.candidate-top { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.member-title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 800; color: #0f172a; }
.member-sub { margin-top: 6px; color: #475569; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.match-box { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: #f8fafc; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.match-label { font-weight: 700; color: #334155; }
code { background: #e2e8f0; padding: 2px 6px; border-radius: 6px; color: #334155; }
@media(max-width: 767px) {
  .card-header, .candidate-top, .search-bar { flex-direction: column; align-items: stretch; }
  .actions { justify-content: flex-start; }
}
</style>
