<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const bindDialogVisible = ref(false)
const formLoading = ref(false)
const bindLoading = ref(false)
const selectedAdmin = ref(null)
const currentUser = ref(null)

const form = reactive({
  username: '',
  password: '',
  display_name: '管理员',
  role: 'admin',
})

const bindForm = reactive({
  openid: '',
})

const loadList = async () => {
  loading.value = true
  try {
    list.value = await request.get('/auth/admins')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载管理员列表失败')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  form.username = ''
  form.password = ''
  form.display_name = '管理员'
  form.role = 'admin'
  dialogVisible.value = true
}

const createAdmin = async () => {
  if (!form.username.trim() || !form.password.trim()) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  formLoading.value = true
  try {
    await request.post('/auth/admins', {
      username: form.username.trim(),
      password: form.password,
      display_name: form.display_name || form.username,
      role: form.role,
    })
    ElMessage.success('管理员创建成功')
    dialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    formLoading.value = false
  }
}

const toggleAdmin = async (row) => {
  try {
    await ElMessageBox.confirm(
      row.is_active ? `确定禁用管理员「${row.display_name}」？` : `确定启用管理员「${row.display_name}」？`,
      '确认操作',
      { type: 'warning' }
    )
    await request.put(`/auth/admins/${row.id}/toggle`)
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    loadList()
  } catch {
    // cancelled or error
  }
}

const openBindDialog = (row) => {
  selectedAdmin.value = row
  bindForm.openid = row.wechat_openid || ''
  bindDialogVisible.value = true
}

const bindWeChat = async () => {
  if (!bindForm.openid.trim()) {
    ElMessage.warning('请输入微信用户的openid')
    return
  }
  bindLoading.value = true
  try {
    await request.post('/auth/bind-wechat', { openid: bindForm.openid.trim() })
    ElMessage.success('绑定成功！管理员在微信小程序中可直接发布官方活动')
    bindDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '绑定失败')
  } finally {
    bindLoading.value = false
  }
}

const roleLabel = (r) => {
  const m = { super_admin: '超级管理员', admin: '管理员' }
  return m[r] || r
}

onMounted(() => {
  try {
    currentUser.value = JSON.parse(localStorage.getItem('yf_admin_user') || '{}')
  } catch { currentUser.value = {} }
  loadList()
})
</script>

<template>
  <el-card class="page-card">
    <template #header>
      <div class="page-toolbar">
        <strong>管理员管理</strong>
        <el-button type="primary" @click="openCreateDialog">新建管理员</el-button>
      </div>
    </template>

    <el-alert title="可创建多个管理员账号，员工登录后可发布活动。绑定微信后，员工在手机小程序中发布的活动会自动标记为「官方」且不需要审核。" type="info" show-icon :closable="false" style="margin-bottom: 16px" />

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="display_name" label="显示名称" min-width="120" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'super_admin' ? 'danger' : 'primary'" size="small">{{ roleLabel(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '正常' : '已禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="微信绑定" min-width="200">
        <template #default="{ row }">
          <span v-if="row.wechat_openid" style="color: #67c23a">已绑定 ({{ row.wechat_openid.substring(0, 12) }}...)</span>
          <span v-else style="color: #909399">未绑定</span>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" min-width="160" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openBindDialog(row)">绑定微信</el-button>
          <el-button
            v-if="currentUser?.id !== row.id"
            size="small"
            :type="row.is_active ? 'warning' : 'success'"
            plain
            @click="toggleAdmin(row)"
          >{{ row.is_active ? '禁用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新建管理员弹窗 -->
  <el-dialog v-model="dialogVisible" title="新建管理员" width="480px" :close-on-click-modal="false">
    <el-form :model="form" label-width="100px">
      <el-form-item label="用户名" required>
        <el-input v-model="form.username" placeholder="登录用，3-50位字母/数字" />
      </el-form-item>
      <el-form-item label="密码" required>
        <el-input v-model="form.password" type="password" placeholder="至少6位" show-password />
      </el-form-item>
      <el-form-item label="显示名称">
        <el-input v-model="form.display_name" placeholder="员工姓名，默认同用户名" />
      </el-form-item>
      <el-form-item label="角色">
        <el-radio-group v-model="form.role">
          <el-radio value="super_admin">超级管理员（全部权限）</el-radio>
          <el-radio value="admin">管理员（业务权限）</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="formLoading" @click="createAdmin">创建</el-button>
    </template>
  </el-dialog>

  <!-- 绑定微信弹窗 -->
  <el-dialog v-model="bindDialogVisible" title="绑定微信" width="480px" :close-on-click-modal="false">
    <el-form :model="bindForm" label-width="100px">
      <el-form-item label="管理员">
        <el-tag>{{ selectedAdmin?.display_name || selectedAdmin?.username }}</el-tag>
      </el-form-item>
      <el-form-item label="微信openid" required>
        <el-input v-model="bindForm.openid" placeholder="输入微信小程序用户的openid" />
      </el-form-item>
    </el-form>
    <p style="color: #909399; font-size: 13px; line-height: 1.6; padding: 0 10px;">
      绑定后，该管理员在微信小程序中发布的活动将自动标记为「官方」并直接上线（无需审核）。
      openid 可在小程序控制台或数据库 users 表查到。
    </p>
    <template #footer>
      <el-button @click="bindDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="bindLoading" @click="bindWeChat">确认绑定</el-button>
    </template>
  </el-dialog>
</template>
