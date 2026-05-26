<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const formLoading = ref(false)
const editingId = ref(null)

const form = reactive({
  title: '',
  content: '',
  link_url: '',
  is_published: false,
  sort_order: 0,
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/cms/announcements')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载公告列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.title = ''
  form.content = ''
  form.link_url = ''
  form.is_published = false
  form.sort_order = 0
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  form.link_url = row.link_url || ''
  form.is_published = row.is_published ?? false
  form.sort_order = row.sort_order ?? 0
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  formLoading.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await request.put(`/cms/announcements/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/cms/announcements', payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    formLoading.value = false
  }
}

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除公告「${row.title}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/cms/announcements/${row.id}`)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    // cancelled or error
  }
}

onMounted(loadList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>公告管理</h2>
      <el-button type="primary" @click="openCreate">新建公告</el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="内容摘要" min-width="200">
        <template #default="{ row }">
          <span class="content-summary">{{ row.content?.substring(0, 80) }}{{ row.content?.length > 80 ? '...' : '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="发布状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_published ? 'success' : 'info'" size="small">{{ row.is_published ? '已发布' : '草稿' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="70" align="center" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑公告' : '新建公告'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="公告标题" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="6" placeholder="公告内容" />
        </el-form-item>
        <el-form-item label="链接 URL">
          <el-input v-model="form.link_url" placeholder="点击跳转链接（可选）" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="发布">
          <el-switch v-model="form.is_published" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.content-summary { color: #666; font-size: 13px; }
</style>
