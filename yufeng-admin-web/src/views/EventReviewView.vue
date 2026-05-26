<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const filters = reactive({ status_filter: 'pending_review', keyword: '', page: 1, page_size: 10, official_only: false })

// ====== 显示报名数编辑弹窗 ======
const displayDialogVisible = ref(false)
const displayForm = reactive({ event_id: null, event_title: '', display_registrant_count: null })

const openDisplayDialog = (row) => {
  displayForm.event_id = row.id
  displayForm.event_title = row.title
  displayForm.display_registrant_count = row.display_registrant_count ?? null
  displayDialogVisible.value = true
}

const saveDisplayCount = async () => {
  try {
    await request.put(`/events/${displayForm.event_id}/display-count`, {
      display_registrant_count: displayForm.display_registrant_count
    })
    ElMessage.success('显示报名数已更新')
    displayDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  }
}

const loadList = async () => {
  loading.value = true
  try {
    const data = await request.get('/events', { params: filters })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载活动列表失败')
  } finally {
    loading.value = false
  }
}

const review = async (row, action) => {
  let rejectReason = ''
  if (action === 'reject') {
    const res = await ElMessageBox.prompt('请输入驳回原因', '驳回活动', { inputValue: '活动信息不完整' })
    rejectReason = res.value
  }
  await request.post(`/events/${row.id}/review`, null, { params: { action, reject_reason: rejectReason } })
  ElMessage.success(action === 'approve' ? '活动已通过' : '活动已驳回')
  loadList()
}

// ====== 官方活动发布弹窗 ======
const dialogVisible = ref(false)
const formLoading = ref(false)
const form = reactive({
  title: '',
  description: '',
  category: '其他',
  cover_image: '',
  location_name: '',
  address: '',
  start_time: '',
  end_time: '',
  registration_deadline: '',
  max_participants: null,
  price: 0,
})
const categoryOptions = ['微醺局', '徒步局', '唱歌局', '相亲局', '沙龙局', '桌游局', '运动', '旅行', '音乐', '户外', '其他']

const openCreateDialog = () => {
  form.title = ''
  form.description = ''
  form.category = '其他'
  form.cover_image = ''
  form.location_name = ''
  form.address = ''
  form.start_time = ''
  form.end_time = ''
  form.registration_deadline = ''
  form.max_participants = null
  form.price = 0
  dialogVisible.value = true
}

const createOfficialEvent = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入活动标题')
    return
  }
  if (!form.start_time) {
    ElMessage.warning('请选择活动开始时间')
    return
  }
  formLoading.value = true
  try {
    const payload = {
      title: form.title.trim(),
      description: form.description,
      category: form.category,
      cover_image: form.cover_image,
      location_name: form.location_name,
      address: form.address,
      start_time: form.start_time,
      end_time: form.end_time || null,
      registration_deadline: form.registration_deadline || null,
      max_participants: form.max_participants || null,
      price: form.price || 0,
    }
    await request.post('/events', payload)
    ElMessage.success('官方活动发布成功！')
    dialogVisible.value = false
    filters.status_filter = 'published'
    filters.official_only = true
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发布失败')
  } finally {
    formLoading.value = false
  }
}

// ====== 删除活动 ======
const deleteEvent = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除活动「${row.title}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/events/${row.id}`)
    ElMessage.success('已删除')
    loadList()
  } catch {
    // cancelled
  }
}

const statusTag = (s) => {
  const m = { draft: 'info', pending_review: 'warning', published: 'success', rejected: 'danger', cancelled: 'info', ended: 'info' }
  return m[s] || 'info'
}

const statusLabel = (s) => {
  const m = { draft: '草稿', pending_review: '待审核', published: '已发布', rejected: '已驳回', cancelled: '已取消', ended: '已结束' }
  return m[s] || s
}

onMounted(loadList)
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar">
        <strong>活动管理</strong>
        <el-button type="primary" @click="openCreateDialog">发布官方活动</el-button>
      </div>
    </template>

    <div class="filter-bar">
      <el-select v-model="filters.status_filter" style="width: 160px" @change="loadList">
        <el-option label="待审核" value="pending_review" />
        <el-option label="已发布" value="published" />
        <el-option label="已驳回" value="rejected" />
        <el-option label="全部" value="all" />
      </el-select>
      <el-checkbox v-model="filters.official_only" style="margin-left: 12px" @change="loadList">仅官方活动</el-checkbox>
      <el-input v-model="filters.keyword" placeholder="搜索活动名/主办方/ID" style="width: 260px; margin-left: 12px" @keyup.enter="loadList" />
      <el-button type="primary" @click="loadList">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="活动标题" min-width="200">
        <template #default="{ row }">
          <span>{{ row.title }}</span>
          <el-tag v-if="row.is_official" size="small" type="danger" style="margin-left: 6px">官方</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="publisher_nickname" label="发布者" min-width="100" />
      <el-table-column prop="category" label="分类" width="80" />
      <el-table-column prop="price" label="价格" width="80">
        <template #default="{ row }">{{ row.price > 0 ? '¥' + row.price : '免费' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="registrant_count" label="报名" width="60" />
      <el-table-column prop="start_time" label="开始时间" min-width="160" />
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button type="success" size="small" :disabled="row.status !== 'pending_review'" @click="review(row, 'approve')">通过</el-button>
          <el-button type="danger" size="small" :disabled="row.status !== 'pending_review'" @click="review(row, 'reject')">驳回</el-button>
          <el-button type="warning" size="small" plain @click="openDisplayDialog(row)">显示数</el-button>
          <el-button type="danger" size="small" plain @click="deleteEvent(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, prev, pager, next" :current-page="filters.page" :page-size="filters.page_size" :total="total" @current-change="(page) => { filters.page = page; loadList() }" />
    </div>
  </el-card>

  <!-- 发布官方活动弹窗 -->
  <el-dialog v-model="dialogVisible" title="发布官方活动" width="600px" :close-on-click-modal="false">
    <el-form :model="form" label-width="110px">
      <el-form-item label="活动标题" required>
        <el-input v-model="form.title" placeholder="请输入活动标题" maxlength="100" />
      </el-form-item>
      <el-form-item label="活动分类">
        <el-select v-model="form.category" style="width: 100%">
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="活动描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="活动描述、须知等" />
      </el-form-item>
      <el-form-item label="封面图URL">
        <el-input v-model="form.cover_image" placeholder="可选，活动封面图片链接" />
      </el-form-item>
      <el-form-item label="活动地点">
        <el-input v-model="form.location_name" placeholder="如：广州天河体育中心" />
      </el-form-item>
      <el-form-item label="详细地址">
        <el-input v-model="form.address" placeholder="可选，具体门牌号" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="开始时间" required>
            <el-date-picker v-model="form.start_time" type="datetime" placeholder="选择开始时间" style="width: 100%" value-format="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="结束时间">
            <el-date-picker v-model="form.end_time" type="datetime" placeholder="可选结束时间" style="width: 100%" value-format="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="报名截止">
            <el-date-picker v-model="form.registration_deadline" type="datetime" placeholder="可选截止时间" style="width: 100%" value-format="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="最大人数">
            <el-input-number v-model="form.max_participants" :min="0" placeholder="不限" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="费用(元)">
        <el-input-number v-model="form.price" :min="0" :precision="2" placeholder="0=免费" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="formLoading" @click="createOfficialEvent">发布</el-button>
    </template>
  </el-dialog>
  <!-- 修改显示报名数弹窗 -->
  <el-dialog v-model="displayDialogVisible" title="修改显示报名数" width="400px" :close-on-click-modal="false">
    <p style="margin-bottom: 16px; color: #666;">活动：<strong>{{ displayForm.event_title }}</strong></p>
    <el-form :model="displayForm" label-width="120px">
      <el-form-item label="显示报名数">
        <el-input-number v-model="displayForm.display_registrant_count" :min="0" :max="9999" placeholder="留空则显示实际人数" style="width: 100%" />
      </el-form-item>
      <p style="color: #999; font-size: 13px; margin: 0 0 0 120px;">留空或不填 = 显示实际报名人数</p>
    </el-form>
    <template #footer>
      <el-button @click="displayDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveDisplayCount">保存</el-button>
    </template>
  </el-dialog>
</template>
