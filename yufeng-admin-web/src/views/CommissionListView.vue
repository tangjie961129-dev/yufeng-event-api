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
    const data = await request.get('/commissions', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载佣金台账失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>佣金台账</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="全部状态" value="all" />
        <el-option label="待结算" value="pending" />
        <el-option label="已结算" value="settled" />
        <el-option label="已失效" value="cancelled" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索分销员/来源类型/备注/流水ID" style="width: 320px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="流水ID" width="90" />
      <el-table-column prop="distributor_name" label="分销员" min-width="120" />
      <el-table-column prop="invited_user_name" label="邀请用户" min-width="120" />
      <el-table-column prop="event_registration_id" label="订单ID" min-width="100" />
      <el-table-column prop="source_type" label="来源" min-width="100" />
      <el-table-column prop="status" label="状态" min-width="100" />
      <el-table-column prop="amount" label="佣金金额" min-width="110" />
      <el-table-column prop="rate" label="比例(%)" min-width="100" />
      <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
      <el-table-column prop="settled_at" label="结算时间" min-width="180" />
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>
