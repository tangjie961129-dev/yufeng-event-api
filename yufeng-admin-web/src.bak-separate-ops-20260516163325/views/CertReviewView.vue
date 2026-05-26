<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const filters = reactive({ status_filter: 'pending', keyword: '', page: 1, page_size: 10 })

const loadList = async () => {
  loading.value = true
  try {
    const data = await request.get('/certs', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载认证列表失败')
  } finally {
    loading.value = false
  }
}

const review = async (row, action) => {
  let rejectReason = ''
  if (action === 'reject') {
    const res = await ElMessageBox.prompt('请输入驳回原因', '驳回认证', { inputValue: '资料不完整' })
    rejectReason = res.value
  }
  await request.post(`/certs/${row.id}/review`, { action, reject_reason: rejectReason })
  ElMessage.success(action === 'approve' ? '已通过认证' : '已驳回认证')
  loadList()
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>主办方认证审核</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
        <el-option label="全部" value="all" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索姓名/手机号/昵称" style="width: 260px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="nickname" label="昵称" min-width="120" />
      <el-table-column prop="real_name" label="真实姓名" min-width="120" />
      <el-table-column prop="phone" label="手机号" min-width="140" />
      <el-table-column prop="status" label="状态" min-width="100" />
      <el-table-column prop="created_at" label="申请时间" min-width="180" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="success" size="small" :disabled="row.status !== 'pending'" @click="review(row, 'approve')">通过</el-button>
          <el-button type="danger" size="small" :disabled="row.status !== 'pending'" @click="review(row, 'reject')">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>
