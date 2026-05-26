<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const applications = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('all')
const keyword = ref('')

const stats = ref({ total: 0, pending: 0, approved: 0, rejected: 0, reviewing: 0 })

const statusOptions = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待审核' },
  { value: 'reviewing', label: '审核中' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'closed', label: '已关闭' },
]

const statusMap = {
  pending: { label: '待审核', type: 'warning' },
  reviewing: { label: '审核中', type: 'primary' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  closed: { label: '已关闭', type: 'info' },
}

// 详情弹窗
const detailVisible = ref(false)
const detailItem = ref(null)

// 审核弹窗
const reviewVisible = ref(false)
const reviewItem = ref(null)
const reviewData = ref({
  status: '',
  admin_note: '',
  reject_reason: '',
})

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value !== 'all') params.status = statusFilter.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const res = await request.get('/cooperations', { params })
    applications.value = res.items || []
    total.value = res.total || 0
  } catch (err) {
    ElMessage.error('加载失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await request.get('/cooperations/stats')
    stats.value = res
  } catch {
    // stats non-critical
  }
}

function showDetail(item) {
  detailItem.value = item
  detailVisible.value = true
}

function showReview(item) {
  reviewItem.value = item
  reviewData.value = {
    status: item.status,
    admin_note: item.admin_note || '',
    reject_reason: item.reject_reason || '',
  }
  reviewVisible.value = true
}

async function submitReview() {
  if (!reviewData.value.status) {
    ElMessage.warning('请选择审核状态')
    return
  }
  try {
    const actionMap = {
      approved: 'approve',
      rejected: 'reject',
      closed: 'close',
    }
    const action = actionMap[reviewData.value.status]
    if (action) {
      const payload = { action }
      if (reviewData.value.admin_note) payload.admin_note = reviewData.value.admin_note
      if (reviewData.value.reject_reason) payload.reject_reason = reviewData.value.reject_reason
      await request.post(`/cooperations/${reviewItem.value.id}/review`, payload)
    } else if (reviewData.value.status === 'reviewing') {
      await request.put(`/cooperations/${reviewItem.value.id}/note`, {
        admin_note: reviewData.value.admin_note || '已标记为审核中，请继续跟进',
      })
    } else {
      throw new Error('不支持的审核状态')
    }
    ElMessage.success('操作成功')
    reviewVisible.value = false
    fetchList()
    fetchStats()
  } catch (err) {
    ElMessage.error('操作失败: ' + (err.response?.data?.detail || err.message))
  }
}

function onSearch() {
  page.value = 1
  fetchList()
}

function onStatusChange(val) {
  statusFilter.value = val
  page.value = 1
  fetchList()
}

function onPageChange(p) {
  page.value = p
  fetchList()
}

function formatTime(t) {
  if (!t) return '-'
  return t.substring(0, 19).replace('T', ' ')
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<template>
  <div class="cooperation-admin">
    <div class="page-header">
      <h2>合作推广管理</h2>
      <p class="page-desc">查看用户提交的合作推广申请，进行审核跟进</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4" v-for="s in [
        { label: '全部', value: stats.total, color: '#909399' },
        { label: '待审核', value: stats.pending, color: '#e6a23c' },
        { label: '审核中', value: stats.reviewing, color: '#409eff' },
        { label: '已通过', value: stats.approved, color: '#67c23a' },
        { label: '已驳回', value: stats.rejected, color: '#f56c6c' },
      ]" :key="s.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-row :gutter="12">
        <el-col :span="6">
          <el-select v-model="statusFilter" placeholder="筛选状态" @change="onStatusChange" style="width:100%">
            <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-col>
        <el-col :span="12">
          <el-input v-model="keyword" placeholder="搜索姓名/手机号/微信号/资源名称" clearable @keyup.enter="onSearch" />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="onSearch">搜索</el-button>
          <el-button @click="fetchList">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never">
      <el-table :data="applications" v-loading="loading" stripe style="width:100%">
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="联系人" prop="name" width="100" />
        <el-table-column label="手机号" prop="phone" width="130" />
        <el-table-column label="微信号" prop="wechat" width="140" />
        <el-table-column label="资源类型" prop="resource_type" width="100" />
        <el-table-column label="资源名称" prop="resource_name" min-width="160">
          <template #default="{ row }">
            <span v-if="row.resource_name">{{ row.resource_name }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="粉丝数" prop="followers" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
            <el-button size="small" type="primary" @click="showReview(row)">审核</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          background
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="申请详情" width="640px">
      <template v-if="detailItem">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="申请ID">{{ detailItem.id }}</el-descriptions-item>
          <el-descriptions-item label="用户ID">{{ detailItem.user_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系人">{{ detailItem.name }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detailItem.phone }}</el-descriptions-item>
          <el-descriptions-item label="微信号">{{ detailItem.wechat }}</el-descriptions-item>
          <el-descriptions-item label="资源类型">{{ detailItem.resource_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="资源名称" :span="2">{{ detailItem.resource_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="粉丝/订阅" :span="2">{{ detailItem.followers || '-' }}</el-descriptions-item>
          <el-descriptions-item label="资源描述" :span="2">{{ detailItem.resource_desc || '-' }}</el-descriptions-item>
          <el-descriptions-item label="合作意向" :span="2">{{ detailItem.coop_intent || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusMap[detailItem.status]?.type || 'info'" size="small">
              {{ statusMap[detailItem.status]?.label || detailItem.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="跟进次数">{{ detailItem.follow_up_count }}</el-descriptions-item>
          <el-descriptions-item label="管理员备注" :span="2">{{ detailItem.admin_note || '-' }}</el-descriptions-item>
          <el-descriptions-item label="驳回原因" :span="2">{{ detailItem.reject_reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatTime(detailItem.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(detailItem.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="审核时间" :span="2">{{ formatTime(detailItem.reviewed_at) }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>

    <!-- 审核弹窗 -->
    <el-dialog v-model="reviewVisible" title="审核申请" width="500px">
      <template v-if="reviewItem">
        <el-form :model="reviewData" label-width="100px">
          <el-form-item label="当前状态">
            <el-tag :type="statusMap[reviewItem.status]?.type || 'info'">
              {{ statusMap[reviewItem.status]?.label || reviewItem.status }}
            </el-tag>
          </el-form-item>
          <el-form-item label="申请人">
            {{ reviewItem.name }}（{{ reviewItem.phone }}）
          </el-form-item>
          <el-form-item label="审核结果" required>
            <el-radio-group v-model="reviewData.status">
              <el-radio value="approved">通过</el-radio>
              <el-radio value="rejected">驳回</el-radio>
              <el-radio value="reviewing">标记审核中</el-radio>
              <el-radio value="closed">关闭</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="驳回原因" v-if="reviewData.status === 'rejected'">
            <el-input v-model="reviewData.reject_reason" type="textarea" :rows="3" placeholder="请填写驳回原因" />
          </el-form-item>
          <el-form-item label="管理员备注">
            <el-input v-model="reviewData.admin_note" type="textarea" :rows="3" placeholder="内部备注，申请人不显示" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReview">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cooperation-admin {
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.page-desc {
  margin: 0;
  color: #909399;
  font-size: 14px;
}
.stats-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  border-radius: 8px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.search-card {
  margin-bottom: 16px;
}
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.empty-text {
  color: #c0c4cc;
}
</style>
