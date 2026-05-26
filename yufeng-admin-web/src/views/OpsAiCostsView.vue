<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const summary = ref(null)
const logs = ref([])
const rules = ref([])

async function loadAll() {
  loading.value = true
  try {
    const [s, l, r] = await Promise.all([
      request.get('/ops/ai-usage/summary'),
      request.get('/ops/ai-usage/logs?limit=120'),
      request.get('/ops/ai-cost-rules'),
    ])
    summary.value = s
    logs.value = l.items || []
    rules.value = r.items || []
  } finally {
    loading.value = false
  }
}

function money(v) { return `¥${Number(v || 0).toFixed(4)}` }
async function saveRule(row) {
  await request.put(`/ops/ai-cost-rules/${row.id}`, {
    prompt_cny_per_m: Number(row.prompt_cny_per_m || 0),
    completion_cny_per_m: Number(row.completion_cny_per_m || 0),
    notes: row.notes || '',
    enabled: !!row.enabled,
  })
  ElMessage.success('成本规则已保存')
  await loadAll()
}
async function reprice() {
  const res = await request.post('/ops/ai-usage/reprice')
  ElMessage.success(`已重算 ${res.updated || 0} 条记录`)
  await loadAll()
}

onMounted(loadAll)
</script>

<template>
  <div class="cost-page" v-loading="loading">
    <div class="page-head">
      <div>
        <p class="eyebrow">AI FINANCE</p>
        <h1>AI 成本核算</h1>
        <p>按模型和业务场景统计 token、调用次数、失败次数和估算成本。</p>
      </div>
      <div class="actions"><el-button @click="reprice">按价格规则重算</el-button><el-button type="primary" @click="loadAll">刷新</el-button></div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="8"><el-card shadow="never" class="metric"><span>今日成本</span><strong>{{ money(summary?.today?.cost_cny) }}</strong><em>{{ summary?.today?.total_tokens || 0 }} tokens</em></el-card></el-col>
      <el-col :xs="24" :sm="8"><el-card shadow="never" class="metric"><span>昨日成本</span><strong>{{ money(summary?.yesterday?.cost_cny) }}</strong><em>{{ summary?.yesterday?.total_tokens || 0 }} tokens</em></el-card></el-col>
      <el-col :xs="24" :sm="8"><el-card shadow="never" class="metric"><span>本月成本</span><strong>{{ money(summary?.month?.cost_cny) }}</strong><em>{{ summary?.month?.calls || 0 }} 次调用</em></el-card></el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>按模型统计（本月）</template>
          <el-table :data="summary?.by_model || []" border>
            <el-table-column prop="key" label="模型" />
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column prop="total_tokens" label="Token" width="110" />
            <el-table-column label="成本" width="110"><template #default="{ row }">{{ money(row.cost_cny) }}</template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>按场景统计（本月）</template>
          <el-table :data="summary?.by_scene || []" border>
            <el-table-column prop="key" label="场景" />
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column prop="total_tokens" label="Token" width="110" />
            <el-table-column label="成本" width="110"><template #default="{ row }">{{ money(row.cost_cny) }}</template></el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>模型价格规则（人民币 / 100万 tokens）</template>
      <el-table :data="rules" border>
        <el-table-column prop="provider" label="供应商" width="140" />
        <el-table-column prop="model" label="模型" width="180" />
        <el-table-column label="输入价"><template #default="{ row }"><el-input-number v-model="row.prompt_cny_per_m" :min="0" :precision="4" /></template></el-table-column>
        <el-table-column label="输出价"><template #default="{ row }"><el-input-number v-model="row.completion_cny_per_m" :min="0" :precision="4" /></template></el-table-column>
        <el-table-column label="启用" width="90"><template #default="{ row }"><el-switch v-model="row.enabled" /></template></el-table-column>
        <el-table-column prop="notes" label="备注" min-width="220"><template #default="{ row }"><el-input v-model="row.notes" /></template></el-table-column>
        <el-table-column label="操作" width="90"><template #default="{ row }"><el-button size="small" type="primary" @click="saveRule(row)">保存</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>最近 Token 消耗明细</template>
      <el-table :data="logs" border>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="scene" label="场景" width="140" />
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column prop="prompt_tokens" label="输入" width="80" />
        <el-table-column prop="completion_tokens" label="输出" width="80" />
        <el-table-column prop="total_tokens" label="总Token" width="90" />
        <el-table-column label="成本" width="100"><template #default="{ row }">{{ money(row.cost_cny) }}</template></el-table-column>
        <el-table-column label="估算" width="80"><template #default="{ row }"><el-tag :type="row.estimated ? 'warning' : 'success'">{{ row.estimated ? '估算' : '真实' }}</el-tag></template></el-table-column>
        <el-table-column prop="response_preview" label="摘要" min-width="260" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.cost-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-head h1 { margin: 4px 0 8px; font-size: 28px; }
.page-head p { margin: 0; color: #64748b; }
.eyebrow { color: #0f766e !important; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.actions { display: flex; gap: 8px; }
.metric span, .metric em { display: block; color: #64748b; font-style: normal; }
.metric strong { display: block; margin: 8px 0; font-size: 28px; color: #0f172a; }
@media (max-width: 767px) { .page-head { flex-direction: column; } }
</style>
