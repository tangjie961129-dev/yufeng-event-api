<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const detailData = ref(null)

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/love/matches')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载匹配记录失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  detailData.value = row
  dialogVisible.value = true
}

onMounted(loadList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>匹配记录</h2>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="user_id" label="用户 ID" width="100" />
      <el-table-column label="匹配类型" width="120">
        <template #default="{ row }">
          <el-tag :type="row.match_type === 'portrait' ? 'warning' : 'primary'" size="small">{{ row.match_type || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="表单数据摘要" min-width="200">
        <template #default="{ row }">
          <span class="summary-text">{{ row.form_data ? JSON.stringify(row.form_data).substring(0, 80) + '...' : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">查看详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="匹配详情" width="600px">
      <template v-if="detailData">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户 ID">{{ detailData.user_id }}</el-descriptions-item>
          <el-descriptions-item label="匹配类型">{{ detailData.match_type }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.created_at }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin-top: 16px; margin-bottom: 8px;">完整表单数据</h4>
        <pre class="form-data-pre">{{ JSON.stringify(detailData.form_data, null, 2) }}</pre>
      </template>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.summary-text { color: #666; font-size: 13px; }
.form-data-pre { background: #f5f5f5; border-radius: 4px; padding: 12px; font-size: 13px; max-height: 400px; overflow-y: auto; }
</style>
