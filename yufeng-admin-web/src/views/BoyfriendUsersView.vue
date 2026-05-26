<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])
const chatDialogVisible = ref(false)
const chatRecords = ref([])
const chatLoading = ref(false)
const currentBoyfriend = ref(null)

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/love/boyfriend')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载 AI 男友用户列表失败')
  } finally {
    loading.value = false
  }
}

const viewChatRecords = async (row) => {
  currentBoyfriend.value = row
  chatDialogVisible.value = true
  chatLoading.value = true
  try {
    const res = await request.get(`/love/boyfriend/${row.id}/chats`)
    chatRecords.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载对话记录失败')
    chatRecords.value = []
  } finally {
    chatLoading.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>AI 男友用户管理</h2>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="user_id" label="用户 ID" width="100" />
      <el-table-column prop="boyfriend_name" label="男友名称" min-width="120" />
      <el-table-column prop="level" label="等级" width="70" align="center" />
      <el-table-column prop="experience" label="经验" width="80" align="center" />
      <el-table-column prop="intimacy" label="亲密度" width="80" align="center" />
      <el-table-column label="是否唤醒" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_interaction_at" label="最后操作时间" min-width="160" />
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewChatRecords(row)">对话记录</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="chatDialogVisible" :title="currentBoyfriend ? `对话记录 - ${currentBoyfriend.boyfriend_name}` : '对话记录'" width="700px">
      <div v-loading="chatLoading">
        <div v-if="chatRecords.length === 0 && !chatLoading" class="empty-tip">暂无对话记录</div>
        <div v-for="(record, idx) in chatRecords" :key="idx" class="chat-item">
          <div class="chat-role" :class="record.role">
            <strong>{{ record.role === 'user' ? '用户' : 'AI 男友' }}</strong>
            <span class="chat-time">{{ record.created_at || '' }}</span>
          </div>
          <div class="chat-content">{{ record.content }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="chatDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.empty-tip { text-align: center; color: #999; padding: 40px 0; }
.chat-item { border-bottom: 1px solid #f0f0f0; padding: 12px 0; }
.chat-role { margin-bottom: 4px; }
.chat-role.user { color: #409eff; }
.chat-role.assistant { color: #67c23a; }
.chat-time { font-size: 12px; color: #999; margin-left: 8px; font-weight: normal; }
.chat-content { color: #333; line-height: 1.6; }
</style>
