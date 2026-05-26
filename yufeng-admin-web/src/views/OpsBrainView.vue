<script setup>
import { onMounted, ref } from 'vue'
import request from '../utils/request'

const loading = ref(false)
const data = ref(null)

async function loadAll() {
  loading.value = true
  try {
    data.value = await request.get('/ops/brain/summary')
  } finally {
    loading.value = false
  }
}

function statusType(v) { return v === 'active' || v === true ? 'success' : 'danger' }
function money(v) { return `¥${Number(v || 0).toFixed(4)}` }

onMounted(loadAll)
</script>

<template>
  <div class="brain-page" v-loading="loading">
    <div class="hero">
      <div>
        <p class="eyebrow">YUFENG OPS BRAIN</p>
        <h1>运营大脑</h1>
        <p>集中看客服大脑、Hermes / GBrain 状态、AI 调用量、成本和最近执行日志。</p>
      </div>
      <el-button type="primary" round @click="loadAll">刷新</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric"><span>今日调用</span><strong>{{ data?.today?.calls || 0 }}</strong><em>失败 {{ data?.today?.failed_calls || 0 }}</em></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric"><span>今日 Token</span><strong>{{ data?.today?.total_tokens || 0 }}</strong><em>估算+真实混合</em></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric"><span>今日成本</span><strong>{{ money(data?.today?.cost_cny) }}</strong><em>按后台价格规则</em></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric"><span>本月成本</span><strong>{{ money(data?.month?.cost_cny) }}</strong><em>{{ data?.month?.total_tokens || 0 }} tokens</em></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>系统健康</template>
          <div class="status-line" v-for="s in data?.system?.services || []" :key="s.name">
            <span>{{ s.name }}</span><el-tag :type="statusType(s.status)">{{ s.status }}</el-tag>
          </div>
          <div class="status-line" v-for="p in data?.system?.ports || []" :key="p.port">
            <span>{{ p.name }} :{{ p.port }}</span><el-tag :type="statusType(p.listening)">{{ p.listening ? 'listening' : 'down' }}</el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>客服大脑沉淀</template>
          <div class="status-line"><span>话术规则</span><strong>{{ data?.counts?.playbooks || 0 }}</strong></div>
          <div class="status-line"><span>助手日志</span><strong>{{ data?.counts?.assistant_logs || 0 }}</strong></div>
          <div class="status-line"><span>反馈记录</span><strong>{{ data?.counts?.feedback_logs || 0 }}</strong></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>朋友圈任务</template>
          <div class="status-line"><span>文案</span><strong>{{ data?.system?.daily?.text_ok || 0 }}/4</strong></div>
          <div class="status-line"><span>配图</span><strong>{{ data?.system?.daily?.image_ok || 0 }}/4</strong></div>
          <div class="status-line"><span>最近状态</span><strong>{{ data?.system?.daily?.status || 'unknown' }}</strong></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>最近 AI 调用</template>
      <el-table :data="data?.recent_usage || []" border>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="scene" label="场景" width="140" />
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column prop="employee_userid" label="员工" width="100" />
        <el-table-column prop="total_tokens" label="Token" width="90" />
        <el-table-column label="成本" width="100"><template #default="{ row }">{{ money(row.cost_cny) }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag></template></el-table-column>
        <el-table-column prop="response_preview" label="回复摘要" min-width="260" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.brain-page { display: flex; flex-direction: column; gap: 16px; }
.hero { color: #fff; background: linear-gradient(135deg, #0f172a, #0f766e); border-radius: 22px; padding: 24px; display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.eyebrow { color: #99f6e4; letter-spacing: .12em; font-weight: 800; margin: 0 0 8px; }
.hero h1 { margin: 0 0 8px; font-size: 32px; }
.hero p { margin: 0; color: #dbeafe; }
.metric { border-radius: 18px; }
.metric span, .metric em { display: block; color: #64748b; font-style: normal; }
.metric strong { display: block; margin: 8px 0; font-size: 28px; color: #0f172a; }
.status-line { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.status-line:last-child { border-bottom: 0; }
@media (max-width: 767px) { .hero { flex-direction: column; } }
</style>
