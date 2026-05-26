<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const bonusLoading = ref(false)
const overview = ref({})
const agents = ref([])
const bindings = ref([])
const bonuses = ref([])
const agentTotal = ref(0)
const bindingTotal = ref(0)
const bonusTotal = ref(0)

const agentFilters = reactive({ keyword: '', status_filter: 'all', page: 1, page_size: 10 })
const bindingFilters = reactive({ keyword: '', binding_type: 'all', status_filter: 'all', page: 1, page_size: 10 })
const bonusFilters = reactive({ quarter: 'all', status_filter: 'all', page: 1, page_size: 10 })

const money = (value) => Number(value || 0).toFixed(2)
const rate = (value) => `${Number(value || 0).toFixed(0)}%`

const loadOverview = async () => {
  overview.value = await request.get('/formal/agent-team-overview')
}

const loadAgents = async () => {
  loading.value = true
  try {
    const data = await request.get('/formal/agents', { params: agentFilters })
    agents.value = data.items || []
    agentTotal.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载合伙人/推广员失败')
  } finally {
    loading.value = false
  }
}

const loadBindings = async () => {
  loading.value = true
  try {
    const data = await request.get('/formal/referral-bindings', { params: bindingFilters })
    bindings.value = data.items || []
    bindingTotal.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载归因绑定失败')
  } finally {
    loading.value = false
  }
}

const loadBonuses = async () => {
  bonusLoading.value = true
  try {
    const data = await request.get('/formal/agent-team-management-bonuses', { params: bonusFilters })
    bonuses.value = data.items || []
    bonusTotal.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载管理奖池失败')
  } finally {
    bonusLoading.value = false
  }
}

const loadAll = async () => {
  await Promise.all([loadOverview(), loadAgents(), loadBindings(), loadBonuses()])
}

onMounted(loadAll)
</script>

<template>
  <div class="partner-page">
    <el-card class="page-card">
      <template #header>
        <div class="page-toolbar">
          <strong>合伙人体系</strong>
          <el-tag type="success">First Touch 锁客 {{ overview.lockDays || 180 }} 天</el-tag>
          <el-tag type="warning">区域合伙人团队管理奖 {{ overview.managementBaseRate || 10 }}% 固定</el-tag>
          <el-button type="primary" @click="loadAll">刷新</el-button>
        </div>
      </template>

      <el-row :gutter="16" class="stat-row">
        <el-col :span="6">
          <el-statistic title="区域合伙人" :value="overview.regionalPartnerCount || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="推广员" :value="overview.promoterCount || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="有效锁客绑定" :value="overview.activeBindingCount || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="冻结管理奖" :value="overview.frozenManagementBonus || 0" :precision="2" prefix="¥" />
        </el-col>
      </el-row>
    </el-card>

    <el-card class="page-card">
      <template #header><strong>区域合伙人 / 推广员</strong></template>
      <div class="filter-bar">
        <el-select v-model="agentFilters.status_filter" style="width: 140px" @change="loadAgents">
          <el-option label="全部状态" value="all" />
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="已停用" value="disabled" />
        </el-select>
        <el-input v-model="agentFilters.keyword" placeholder="昵称/手机号/代理码/ID" style="width: 280px" @keyup.enter="loadAgents" />
        <el-button type="primary" @click="loadAgents">查询</el-button>
      </div>
      <el-table v-loading="loading" :data="agents" stripe>
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="nickname" label="昵称" min-width="110" />
        <el-table-column prop="agent_code" label="代理码" min-width="120" />
        <el-table-column label="身份" min-width="120">
          <template #default="{ row }">
            <el-tag :type="row.agent_type === 'regional_partner' ? 'warning' : 'info'">
              {{ row.agent_type === 'regional_partner' ? '区域合伙人' : '推广员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="parent_agent_name" label="上级合伙人" min-width="120" />
        <el-table-column prop="service_region" label="服务区域" min-width="120" />
        <el-table-column label="直推分成" width="100"><template #default="{ row }">{{ rate(row.direct_commission_rate) }}</template></el-table-column>
        <el-table-column label="管理奖" width="100"><template #default="{ row }">{{ rate(row.management_base_rate) }}</template></el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status === 'approved' ? 'success' : row.status === 'pending' ? 'warning' : 'info'">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风控" width="100" />
        <el-table-column prop="created_at" label="创建时间" min-width="170" />
      </el-table>
      <div class="table-footer"><el-pagination background layout="total, prev, pager, next" :current-page="agentFilters.page" :page-size="agentFilters.page_size" :total="agentTotal" @current-change="(page) => { agentFilters.page = page; loadAgents() }" /></div>
    </el-card>

    <el-card class="page-card">
      <template #header><strong>First Touch 锁客归因</strong></template>
      <div class="filter-bar">
        <el-select v-model="bindingFilters.status_filter" style="width: 140px" @change="loadBindings">
          <el-option label="全部状态" value="all" />
          <el-option label="已绑定" value="bound" />
          <el-option label="已锁定" value="locked" />
          <el-option label="已失效" value="invalid" />
        </el-select>
        <el-input v-model="bindingFilters.keyword" placeholder="source/活动/用户ID" style="width: 280px" @keyup.enter="loadBindings" />
        <el-button type="primary" @click="loadBindings">查询</el-button>
      </div>
      <el-table v-loading="loading" :data="bindings" stripe>
        <el-table-column prop="invited_user_name" label="客户" min-width="120" />
        <el-table-column prop="inviter_user_name" label="来源代理" min-width="120" />
        <el-table-column prop="source_platform" label="平台" width="110" />
        <el-table-column prop="source_scene" label="scene" min-width="160" />
        <el-table-column prop="lock_days" label="锁客天数" width="100" />
        <el-table-column prop="locked_until" label="锁客到期" min-width="170" />
        <el-table-column label="归因状态" width="110"><template #default="{ row }"><el-tag type="success">{{ row.attribution_status }}</el-tag></template></el-table-column>
        <el-table-column prop="bound_at" label="绑定时间" min-width="170" />
      </el-table>
      <div class="table-footer"><el-pagination background layout="total, prev, pager, next" :current-page="bindingFilters.page" :page-size="bindingFilters.page_size" :total="bindingTotal" @current-change="(page) => { bindingFilters.page = page; loadBindings() }" /></div>
    </el-card>

    <el-card class="page-card">
      <template #header><strong>季度团队管理奖冻结池</strong></template>
      <div class="filter-bar">
        <el-input v-model="bonusFilters.quarter" placeholder="季度，如 2026Q2；all 为全部" style="width: 220px" @keyup.enter="loadBonuses" />
        <el-select v-model="bonusFilters.status_filter" style="width: 140px" @change="loadBonuses">
          <el-option label="全部状态" value="all" />
          <el-option label="冻结中" value="frozen" />
          <el-option label="已结算" value="settled" />
          <el-option label="已冲正" value="reversed" />
        </el-select>
        <el-button type="primary" @click="loadBonuses">查询</el-button>
      </div>
      <el-table v-loading="bonusLoading" :data="bonuses" stripe>
        <el-table-column prop="quarter" label="季度" width="100" />
        <el-table-column prop="regional_partner_name" label="区域合伙人" min-width="120" />
        <el-table-column prop="promoter_name" label="推广员" min-width="120" />
        <el-table-column prop="source_order_id" label="来源订单" min-width="140" />
        <el-table-column label="基数" width="100"><template #default="{ row }">¥{{ money(row.base_amount) }}</template></el-table-column>
        <el-table-column label="固定比例" width="100"><template #default="{ row }">{{ rate(row.base_rate) }}</template></el-table-column>
        <el-table-column label="奖金" width="110"><template #default="{ row }">¥{{ money(row.bonus_amount) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.settlement_status === 'settled' ? 'success' : 'warning'">{{ row.settlement_status }}</el-tag></template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="170" />
      </el-table>
      <div class="table-footer"><el-pagination background layout="total, prev, pager, next" :current-page="bonusFilters.page" :page-size="bonusFilters.page_size" :total="bonusTotal" @current-change="(page) => { bonusFilters.page = page; loadBonuses() }" /></div>
    </el-card>
  </div>
</template>

<style scoped>
.partner-page { display: flex; flex-direction: column; gap: 16px; }
.page-toolbar { display: flex; align-items: center; gap: 12px; }
.stat-row { margin-top: 8px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
