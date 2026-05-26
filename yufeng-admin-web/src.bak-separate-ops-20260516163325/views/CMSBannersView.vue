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
  image_url: '',
  target_url: '',
  page: 'home',
  sort_order: 0,
  is_enabled: true,
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/cms/banners')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载 Banner 列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.title = ''
  form.subtitle = ''
  form.image_url = ''
  form.target_url = ''
  form.page = 'home'
  form.sort_order = 0
  form.is_enabled = true
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.title = row.title || ''
  form.subtitle = row.subtitle || ''
  form.image_url = row.image_url || ''
  form.target_url = row.target_url || ''
  form.page = row.page || 'home'
  form.sort_order = row.sort_order ?? 0
  form.is_enabled = row.is_enabled ?? true
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
      await request.put(`/cms/banners/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/cms/banners', payload)
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
    await ElMessageBox.confirm(`确定删除 Banner「${row.title}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/cms/banners/${row.id}`)
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
      <h2>Banner 管理</h2>
      <el-button type="primary" @click="openCreate">新建 Banner</el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column label="图片预览" width="120">
        <template #default="{ row }">
          <el-image v-if="row.image_url" :src="row.image_url" style="width: 60px; height: 40px" fit="cover" />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="页面" width="90">
        <template #default="{ row }">
          <el-tag size="small">{{ row.page || 'home' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '是' : '否' }}</el-tag>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 Banner' : '新建 Banner'" width="550px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="Banner 标题" />
        </el-form-item>
        <el-form-item label="副标题">
          <el-input v-model="form.subtitle" placeholder="副标题（可选）" />
        </el-form-item>
        <el-form-item label="图片 URL">
          <el-input v-model="form.image_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="跳转 URL">
          <el-input v-model="form.target_url" placeholder="点击跳转链接（可选）" />
        </el-form-item>
        <el-form-item label="所属页面">
          <el-select v-model="form.page">
            <el-option label="首页" value="home" />
            <el-option label="恋爱交友" value="love" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
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
