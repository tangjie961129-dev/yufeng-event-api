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
  subtitle: '',
  description: '',
  cover_url: '',
  category: '',
  price: 0,
  duration: 0,
  instructor: '',
  is_published: false,
  sort_order: 0,
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/courses')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载课程列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.title = ''
  form.subtitle = ''
  form.description = ''
  form.cover_url = ''
  form.category = ''
  form.price = 0
  form.duration = 0
  form.instructor = ''
  form.is_published = false
  form.sort_order = 0
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.title = row.title || ''
  form.subtitle = row.subtitle || ''
  form.description = row.description || ''
  form.cover_url = row.cover_url || ''
  form.category = row.category || ''
  form.price = row.price ?? 0
  form.duration = row.duration ?? 0
  form.instructor = row.instructor || ''
  form.is_published = row.is_published ?? false
  form.sort_order = row.sort_order ?? 0
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  formLoading.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await request.put(`/courses/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/courses', payload)
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
    await ElMessageBox.confirm(`确定删除课程「${row.title}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/courses/${row.id}`)
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
      <h2>课程管理</h2>
      <el-button type="primary" @click="openCreate">新建课程</el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column label="价格" width="90">
        <template #default="{ row }">
          <span>{{ row.price != null ? '¥' + row.price : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="instructor" label="讲师" width="100" />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑课程' : '新建课程'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="课程标题" />
        </el-form-item>
        <el-form-item label="副标题">
          <el-input v-model="form.subtitle" placeholder="副标题（可选）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="课程描述" />
        </el-form-item>
        <el-form-item label="封面 URL">
          <el-input v-model="form.cover_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="如：心理学、情感、沟通" />
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="form.price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="课时">
          <el-input-number v-model="form.duration" :min="0" />
        </el-form-item>
        <el-form-item label="讲师">
          <el-input v-model="form.instructor" placeholder="讲师姓名" />
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
</style>
