<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const filters = reactive({ status_filter: 'all', keyword: '', page: 1, page_size: 10 })

const loadList = async () => {
  loading.value = true
  try {
    const data = await request.get('/orders', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载订单列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>订单台账</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="全部状态" value="all" />
        <el-option label="待支付" value="pending" />
        <el-option label="已支付" value="paid" />
        <el-option label="已核销" value="verified" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索活动/昵称/支付单号/订单ID" style="width: 320px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="订单ID" width="90" />
      <el-table-column prop="event_title" label="活动" min-width="180" />
      <el-table-column prop="user_nickname" label="报名用户" min-width="120" />
      <el-table-column prop="organizer_name" label="主办方" min-width="120" />
      <el-table-column prop="status" label="状态" min-width="100" />
      <el-table-column prop="quantity" label="数量" min-width="80" />
      <el-table-column prop="total_price" label="订单金额" min-width="100" />
      <el-table-column prop="commission_amount" label="抽成金额" min-width="100" />
      <el-table-column prop="payment_id" label="支付单号" min-width="180" />
      <el-table-column prop="paid_at" label="支付时间" min-width="180" />
    </el-table>
    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>
