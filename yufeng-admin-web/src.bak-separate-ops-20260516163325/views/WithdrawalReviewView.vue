<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const actionLoadingId = ref(null)
const list = ref([])
const total = ref(0)
const filters = reactive({ status_filter: 'all', keyword: '', page: 1, page_size: 10 })

const loadList = async () => {
  loading.value = true
  try {
    const data = await request.get('/withdrawals', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载提现申请失败')
  } finally {
    loading.value = false
  }
}

const reviewWithdrawal = async (row, action) => {
  let rejectReason = ''
  if (action === 'reject') {
    try {
      const result = await ElMessageBox.prompt('请输入驳回原因', '驳回提现', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '例如：收款信息不完整',
      })
      rejectReason = result.value || ''
    } catch {
      return
    }
  } else {
    try {
      await ElMessageBox.confirm(`确认将该提现申请标记为${action === 'approve' ? '已审核通过' : '已打款'}吗？`, '操作确认', {
        type: 'warning',
      })
    } catch {
      return
    }
  }

  actionLoadingId.value = row.id
  try {
    await request.post(`/withdrawals/${row.id}/review`, {
      action,
      reject_reason: rejectReason,
    })
    ElMessage.success('提现申请处理成功')
    await loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '处理提现申请失败')
  } finally {
    actionLoadingId.value = null
  }
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>提现审核</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="全部状态" value="all" />
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已打款" value="paid" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索分销员/户名/账号/申请ID" style="width: 320px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="申请ID" width="90" />
      <el-table-column prop="distributor_name" label="分销员" min-width="120" />
      <el-table-column prop="amount" label="提现金额" min-width="100" />
      <el-table-column prop="account_type" label="收款类型" min-width="100" />
      <el-table-column prop="account_name" label="收款户名" min-width="120" />
      <el-table-column prop="account_no" label="收款账号" min-width="180" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" min-width="100" />
      <el-table-column prop="reject_reason" label="驳回原因" min-width="180" show-overflow-tooltip />
      <el-table-column prop="reviewed_admin_name" label="审核人" min-width="120" />
      <el-table-column prop="created_at" label="申请时间" min-width="180" />
      <el-table-column prop="reviewed_at" label="审核时间" min-width="180" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button v-if="row.status === 'pending'" type="success" size="small" :loading="actionLoadingId === row.id" @click="reviewWithdrawal(row, 'approve')">通过</el-button>
            <el-button v-if="row.status === 'pending'" type="danger" size="small" :loading="actionLoadingId === row.id" @click="reviewWithdrawal(row, 'reject')">驳回</el-button>
            <el-button v-if="row.status === 'approved'" type="primary" size="small" :loading="actionLoadingId === row.id" @click="reviewWithdrawal(row, 'paid')">标记已打款</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>

<style scoped>
.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
