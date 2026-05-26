<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const formLoading = ref(false)
const editingId = ref(null)
const pageFilter = ref('')

const widgetTypeOptions = [
  { value: 'hero_banner', label: 'Hero Banner' },
  { value: 'features_grid', label: '功能网格' },
  { value: 'course_list', label: '课程列表' },
  { value: 'activity_list', label: '活动列表' },
  { value: 'quiz_entry', label: '问卷入口' },
]

const form = reactive({
  page: '',
  widget_type: 'hero_banner',
  config: '{}',
  sort_order: 0,
  is_enabled: true,
})

const loadList = async () => {
  loading.value = true
  try {
    const params = {}
    if (pageFilter.value) params.page = pageFilter.value
    const res = await request.get('/cms/widgets', { params })
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载组件列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.page = ''
  form.widget_type = 'hero_banner'
  form.config = '{}'
  form.sort_order = 0
  form.is_enabled = true
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.page = row.page || ''
  form.widget_type = row.widget_type || 'hero_banner'
  form.config = row.config ? JSON.stringify(row.config, null, 2) : '{}'
  form.sort_order = row.sort_order ?? 0
  form.is_enabled = row.is_enabled ?? true
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.page.trim()) {
    ElMessage.warning('请选择页面')
    return
  }
  // validate JSON
  try {
    JSON.parse(form.config)
  } catch {
    ElMessage.warning('配置 JSON 格式不正确')
    return
  }
  formLoading.value = true
  try {
    const payload = {
      ...form,
      config: JSON.parse(form.config),
    }
    if (editingId.value) {
      await request.put(`/cms/widgets/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/cms/widgets', payload)
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
    await ElMessageBox.confirm(`确定删除组件 #${row.id}？`, '确认删除', { type: 'warning' })
    await request.delete(`/cms/widgets/${row.id}`)
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
      <h2>页面组件配置</h2>
      <div class="header-actions">
        <el-input v-model="pageFilter" placeholder="按页面筛选" clearable style="width: 200px; margin-right: 12px;" @clear="loadList" @keyup.enter="loadList" />
        <el-button @click="loadList">筛选</el-button>
        <el-button type="primary" @click="openCreate">新建组件</el-button>
      </div>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="page" label="页面" width="100" />
      <el-table-column label="组件类型" width="140">
        <template #default="{ row }">
          <el-tag size="small">{{ row.widget_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="配置预览" min-width="250">
        <template #default="{ row }">
          <pre class="config-preview">{{ JSON.stringify(row.config, null, 1) }}</pre>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑组件' : '新建组件'" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="页面" required>
          <el-input v-model="form.page" placeholder="页面标识，如 home / love" />
        </el-form-item>
        <el-form-item label="组件类型" required>
          <el-select v-model="form.widget_type" style="width: 100%;">
            <el-option v-for="opt in widgetTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="配置 JSON" required>
          <el-input v-model="form.config" type="textarea" :rows="8" placeholder='{"key": "value"}' />
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
.header-actions { display: flex; align-items: center; }
.config-preview { background: #f5f5f5; border-radius: 4px; padding: 6px 8px; font-size: 12px; max-height: 60px; overflow-y: auto; margin: 0; white-space: pre-wrap; }
</style>
