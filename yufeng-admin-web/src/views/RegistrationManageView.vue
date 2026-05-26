<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const events = ref([])
const filters = reactive({ event_id: '', status_filter: 'all', keyword: '', page: 1, page_size: 10 })
const dialogVisible = ref(false)
const editingReg = ref(null)
const editRemark = ref('')

const loadEvents = async () => {
  try {
    const data = await request.get('/registrations/events')
    events.value = data || []
  } catch { /* ignore */ }
}

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...filters, page_size: filters.page_size, page: filters.page }
    if (filters.event_id) params.event_id = filters.event_id
    const data = await request.get('/registrations', { params })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载报名列表失败')
  } finally {
    loading.value = false
  }
}

const parseRemark = (remark) => {
  if (!remark) return []
  const items = []
  const lines = remark.split('\n')
  let inForm = false
  for (const line of lines) {
    if (line.includes('【报名表】')) { inForm = true; continue }
    if (inForm && line.includes('：')) {
      const parts = line.split('：')
      items.push({ label: parts[0], value: parts.slice(1).join('：') })
    }
  }
  return items
}

const openEdit = (row) => {
  editingReg.value = row
  editRemark.value = row.remark || ''
  dialogVisible.value = true
}

const saveRemark = async () => {
  try {
    await request.put(`/registrations/${editingReg.value.id}/remark`, { remark: editRemark.value })
    ElMessage.success('备注已更新')
    dialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  }
}

onMounted(() => {
  loadEvents()
  loadList()
})
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar"><strong>报名管理</strong></div>
    </template>
    <div class="filter-bar">
      <el-select v-model="filters.event_id" placeholder="选择活动" clearable style="width: 300px" @change="loadList">
        <el-option v-for="ev in events" :key="ev.id" :label="ev.title + ' (' + ev.start_time + ')'" :value="ev.id" />
      </el-select>
      <el-select v-model="filters.status_filter" style="width: 140px" @change="loadList">
        <el-option label="全部状态" value="all" />
        <el-option label="待支付" value="pending" />
        <el-option label="已支付" value="paid" />
        <el-option label="已核销" value="verified" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索昵称/活动/备注" style="width: 260px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="event_title" label="活动" min-width="160" show-overflow-tooltip />
      <el-table-column prop="user_nickname" label="报名用户" min-width="100" />
      <el-table-column prop="status" label="状态" min-width="80" />
      <el-table-column label="报名信息" min-width="280">
        <template #default="{ row }">
          <div v-if="parseRemark(row.remark).length > 0" class="remark-grid">
            <div v-for="item in parseRemark(row.remark)" :key="item.label" class="remark-item">
              <span class="remark-label">{{ item.label }}：</span>
              <span class="remark-value">{{ item.value }}</span>
            </div>
          </div>
          <span v-else class="no-data">无填写信息</span>
        </template>
      </el-table-column>
      <el-table-column prop="total_price" label="费用" width="80">
        <template #default="{ row }">
          {{ row.total_price > 0 ? '¥' + row.total_price : '免费' }}
        </template>
      </el-table-column>
      <el-table-column prop="paid_at" label="支付时间" min-width="150">
        <template #default="{ row }">{{ row.paid_at ? row.paid_at.slice(0, 16) : '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑备注</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>

  <el-dialog v-model="dialogVisible" title="编辑报名备注" width="600px">
    <p v-if="editingReg" style="margin-bottom:12px;color:#666;font-size:13px;">
      活动：{{ editingReg.event_title }} | 用户：{{ editingReg.user_nickname }}
    </p>
    <el-input v-model="editRemark" type="textarea" :rows="8" placeholder="修改报名信息备注…" />
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveRemark">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.remark-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.remark-item {
  font-size: 13px;
  line-height: 1.7;
  white-space: nowrap;
}
.remark-label {
  color: #999;
}
.remark-value {
  color: #333;
  font-weight: 500;
}
.no-data {
  color: #bbb;
  font-size: 13px;
}
</style>
