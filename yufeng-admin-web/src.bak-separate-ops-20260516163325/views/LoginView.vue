<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = ref({ username: 'admin', password: 'admin123456' })

const handleLogin = async () => {
  loading.value = true
  try {
    await authStore.login(form.value)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="title">屿风活动管理后台</div>
      <div class="subtitle">第一版 MVP：审核、订单、数据总览</div>
      <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="账号">
          <el-input v-model="form.username" placeholder="请输入管理员账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width: 100%; margin-top: 8px;" @click="handleLogin">
          登录后台
        </el-button>
      </el-form>
      <div class="hint">默认已初始化：admin / admin123456</div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at top, #1d4ed8, #0f172a 58%);
}
.login-panel {
  width: 420px;
  padding: 36px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.35);
}
.title {
  font-size: 30px;
  font-weight: 700;
  margin-bottom: 8px;
}
.subtitle {
  color: #6b7280;
  margin-bottom: 24px;
}
.hint {
  margin-top: 16px;
  color: #6b7280;
  font-size: 13px;
}
</style>
