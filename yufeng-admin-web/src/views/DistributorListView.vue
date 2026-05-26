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
    const data = await request.get('/distributors', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载分销员列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>分销员管理</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="全部状态" value="all" />
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已拒绝" value="rejected" />
        <el-option label="已停用" value="disabled" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索昵称/手机号/邀请码/ID" style="width: 320px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="档案ID" width="90" />
      <el-table-column prop="user_id" label="用户ID" width="90" />
      <el-table-column prop="nickname" label="昵称" min-width="120" />
      <el-table-column prop="phone" label="手机号" min-width="140" />
      <el-table-column prop="invite_code" label="邀请码" min-width="140" />
      <el-table-column prop="display_name" label="分销显示名" min-width="140" />
      <el-table-column prop="level" label="等级" min-width="100" />
      <el-table-column label="状态" min-width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'pending' ? 'warning' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_invited_users" label="邀请人数" min-width="100" />
      <el-table-column prop="total_paid_orders" label="成单数" min-width="100" />
      <el-table-column prop="total_commission_earned" label="累计佣金" min-width="110" />
      <el-table-column prop="withdrawable_balance" label="可提现余额" min-width="120" />
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>
