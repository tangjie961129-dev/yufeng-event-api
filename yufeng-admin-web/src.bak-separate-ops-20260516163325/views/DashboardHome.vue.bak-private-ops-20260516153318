<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const overview = ref({})
const trendItems = ref([])
const loading = ref(false)

const cards = computed(() => [
  { label: '总用户数', value: overview.value.total_users || 0 },
  { label: '已认证主办方', value: overview.value.total_organizers || 0 },
  { label: '待审活动', value: overview.value.pending_events || 0 },
  { label: '待审主办方', value: overview.value.pending_certs || 0 },
  { label: '累计订单', value: overview.value.total_registrations || 0 },
  { label: '已支付订单', value: overview.value.paid_orders || 0 },
  { label: '总流水(元)', value: overview.value.total_revenue || 0 },
  { label: '平台抽成(元)', value: overview.value.total_commission || 0 },
])

const loadData = async () => {
  loading.value = true
  try {
    const [overviewRes, trendsRes] = await Promise.all([
      request.get('/dashboard/overview'),
      request.get('/dashboard/trends?days=7'),
    ])
    overview.value = overviewRes
    trendItems.value = trendsRes.items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载仪表盘失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div v-loading="loading">
    <div class="stat-grid">
      <div v-for="card in cards" :key="card.label" class="stat-card">
        <div class="label">{{ card.label }}</div>
        <div class="value">{{ card.value }}</div>
      </div>
    </div>

    <el-card class="page-card">
      <template #header>
        <div class="page-toolbar">
          <strong>近 7 日报名趋势</strong>
        </div>
      </template>
      <el-table :data="trendItems" stripe>
        <el-table-column prop="date" label="日期" min-width="160" />
        <el-table-column prop="registrations" label="报名数" min-width="120" />
        <el-table-column prop="revenue" label="流水(元)" min-width="160" />
      </el-table>
    </el-card>
  </div>
</template>
