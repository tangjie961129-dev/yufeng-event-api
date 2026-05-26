<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const filters = reactive({ keyword: '', page: 1, page_size: 10 })

const loadList = async () => {
  loading.value = true
  try {
    const data = await request.get('/users', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>用户管理</strong></div>
    </template>
    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="搜索昵称/手机号/ID" style="width: 260px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="nickname" label="昵称" min-width="160" />
      <el-table-column prop="phone" label="手机号" min-width="140" />
      <el-table-column label="主办方" min-width="100">
        <template #default="{ row }">{{ row.is_organizer ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="已认证" min-width="100">
        <template #default="{ row }">{{ row.organizer_verified ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" min-width="180" />
    </el-table>
    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>
</template>
