<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loadingPermissions = ref(false)
const loadingAdmins = ref(false)
const savingAdmin = ref(false)
const togglingId = ref(null)
const permissions = ref([])
const currentRole = ref('')
const adminList = ref([])
const adminTotal = ref(0)
const createDialogVisible = ref(false)

const filters = reactive({ keyword: '', page: 1, page_size: 10 })
const createForm = reactive({
  username: '',
  password: '',
  display_name: '',
  role: 'operator',
})

const roleOptions = [
  { label: '超级管理员', value: 'super_admin' },
  { label: '运营', value: 'operator' },
  { label: '财务', value: 'finance' },
]

const permissionGroups = computed(() => {
  const map = {}
  for (const item of permissions.value) {
    const prefix = (item.key || '').split('.')[0] || 'other'
    if (!map[prefix]) map[prefix] = []
    map[prefix].push(item)
  }
  return Object.entries(map)
})

const resetCreateForm = () => {
  createForm.username = ''
  createForm.password = ''
  createForm.display_name = ''
  createForm.role = 'operator'
}

const loadPermissions = async () => {
  loadingPermissions.value = true
  try {
    const data = await request.get('/permissions/me')
    permissions.value = data.permissions || []
    currentRole.value = data.role || ''
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载权限失败')
  } finally {
    loadingPermissions.value = false
  }
}

const loadAdmins = async () => {
  loadingAdmins.value = true
  try {
    const data = await request.get('/admin-users', { params: filters })
    adminList.value = data.items || []
    adminTotal.value = data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载后台账号失败')
  } finally {
    loadingAdmins.value = false
  }
}

const openCreateDialog = () => {
  resetCreateForm()
  createDialogVisible.value = true
}

const submitCreate = async () => {
  if (!createForm.username.trim() || !createForm.password.trim()) {
    ElMessage.warning('请填写账号和密码')
    return
  }
  savingAdmin.value = true
  try {
    await request.post('/admin-users', {
      username: createForm.username.trim(),
      password: createForm.password,
      display_name: createForm.display_name.trim() || '管理员',
      role: createForm.role,
    })
    ElMessage.success('后台账号已创建')
    createDialogVisible.value = false
    await loadAdmins()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建后台账号失败')
  } finally {
    savingAdmin.value = false
  }
}

const toggleActive = async (row) => {
  const nextStatus = !row.is_active
  const actionText = nextStatus ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确认${actionText}账号“${row.username}”吗？`, '操作确认', {
      type: 'warning',
    })
  } catch {
    return
  }

  togglingId.value = row.id
  try {
    await request.post(`/admin-users/${row.id}/toggle-active`, { is_active: nextStatus })
    ElMessage.success(`账号已${actionText}`)
    await loadAdmins()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || `${actionText}账号失败`)
  } finally {
    togglingId.value = null
  }
}

onMounted(async () => {
  await loadPermissions()
  await loadAdmins()
})
</script>

<template>
  <div class="page-stack">
    <el-card class="page-card">
      <template #header>
        <div class="page-toolbar">
          <strong>权限概览</strong>
          <el-tag type="primary">当前角色：{{ currentRole || '未识别' }}</el-tag>
        </div>
      </template>

      <el-skeleton :loading="loadingPermissions" animated :rows="4">
        <div class="permission-grid">
          <el-card v-for="([group, items]) in permissionGroups" :key="group" shadow="hover" class="permission-card">
            <template #header>
              <div class="permission-title">{{ group }}</div>
            </template>
            <div class="permission-tags">
              <el-tag v-for="item in items" :key="item.key" class="permission-tag">
                {{ item.name }}
              </el-tag>
            </div>
          </el-card>
        </div>
      </el-skeleton>
    </el-card>

    <el-card class="page-card">
      <template #header>
        <div class="page-toolbar">
          <strong>后台账号管理</strong>
          <el-button type="primary" @click="openCreateDialog">新建账号</el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-input v-model="filters.keyword" placeholder="搜索账号/姓名/角色/ID" style="width: 320px" @keyup.enter="loadAdmins" />
        <el-button type="primary" @click="loadAdmins">查询</el-button>
      </div>

      <el-table v-loading="loadingAdmins" :data="adminList" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="账号" min-width="140" />
        <el-table-column prop="display_name" label="显示名" min-width="140" />
        <el-table-column prop="role" label="角色" min-width="120" />
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用中' : '已禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最近登录" min-width="180" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.is_active ? 'danger' : 'success'"
              :loading="togglingId === row.id"
              @click="toggleActive(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :current-page="filters.page"
          :page-size="filters.page_size"
          :total="adminTotal"
          @current-change="(page) => { filters.page = page; loadAdmins() }"
        />
      </div>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建后台账号" width="520px">
      <el-form label-width="100px">
        <el-form-item label="登录账号">
          <el-input v-model="createForm.username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="登录密码">
          <el-input v-model="createForm.password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="createForm.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingAdmin" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-stack {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}
.permission-card {
  border-radius: 16px;
}
.permission-title {
  font-weight: 700;
  text-transform: capitalize;
}
.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.permission-tag {
  margin: 0;
}
</style>
