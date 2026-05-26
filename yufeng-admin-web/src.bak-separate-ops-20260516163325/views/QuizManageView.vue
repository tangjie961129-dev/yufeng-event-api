<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const list = ref([])

// Quiz dialog
const dialogVisible = ref(false)
const formLoading = ref(false)
const editingId = ref(null)
const form = reactive({
  title: '',
  description: '',
  quiz_type: 'mbti',
  is_published: false,
})

// Questions sub-table
const questionDialogVisible = ref(false)
const questionFormLoading = ref(false)
const questionEditingId = ref(null)
const currentQuizId = ref(null)
const questions = ref([])
const questionForm = reactive({
  question_text: '',
  question_type: 'choice',
  options: '[]',
  sort_order: 0,
})

// Result ranges sub-table
const rangeDialogVisible = ref(false)
const rangeFormLoading = ref(false)
const rangeEditingId = ref(null)
const ranges = ref([])
const rangeForm = reactive({
  label: '',
  min_score: 0,
  max_score: 100,
  description: '',
  result_image: '',
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await request.get('/quizzes')
    list.value = res?.items || res || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载问卷列表失败')
  } finally {
    loading.value = false
  }
}

// ---- Quiz CRUD ----
const openCreate = () => {
  editingId.value = null
  form.title = ''
  form.description = ''
  form.quiz_type = 'mbti'
  form.is_published = false
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.title = row.title || ''
  form.description = row.description || ''
  form.quiz_type = row.quiz_type || 'mbti'
  form.is_published = row.is_published ?? false
  dialogVisible.value = true
}

const submitQuiz = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  formLoading.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await request.put(`/quizzes/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await request.post('/quizzes', payload)
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
    await ElMessageBox.confirm(`确定删除问卷「${row.title}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/quizzes/${row.id}`)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    // cancelled or error
  }
}

// ---- Questions ----
const loadQuestions = async (quizId) => {
  try {
    const res = await request.get(`/quizzes/${quizId}/questions`)
    const data = res?.items || res || []
    questions.value = data.map(q => ({
      ...q,
      options: typeof q.options === 'string' ? q.options : JSON.stringify(q.options || []),
    }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载题目失败')
    questions.value = []
  }
}

const openQuestionCreate = (quizId) => {
  currentQuizId.value = quizId
  questionEditingId.value = null
  questionForm.question_text = ''
  questionForm.question_type = 'choice'
  questionForm.options = '[]'
  questionForm.sort_order = 0
  questionDialogVisible.value = true
}

const openQuestionEdit = (row) => {
  currentQuizId.value = row.quiz_id
  questionEditingId.value = row.id
  questionForm.question_text = row.question_text || ''
  questionForm.question_type = row.question_type || 'choice'
  questionForm.options = row.options || '[]'
  questionForm.sort_order = row.sort_order ?? 0
  questionDialogVisible.value = true
}

const submitQuestion = async () => {
  if (!questionForm.question_text.trim()) {
    ElMessage.warning('请输入题目内容')
    return
  }
  try {
    JSON.parse(questionForm.options)
  } catch {
    ElMessage.warning('选项 JSON 格式不正确')
    return
  }
  questionFormLoading.value = true
  try {
    const payload = {
      ...questionForm,
      options: JSON.parse(questionForm.options),
    }
    if (questionEditingId.value) {
      await request.put(`/quizzes/${currentQuizId.value}/questions/${questionEditingId.value}`, payload)
      ElMessage.success('题目更新成功')
    } else {
      await request.post(`/quizzes/${currentQuizId.value}/questions`, payload)
      ElMessage.success('题目创建成功')
    }
    questionDialogVisible.value = false
    loadQuestions(currentQuizId.value)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存题目失败')
  } finally {
    questionFormLoading.value = false
  }
}

const removeQuestion = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除题目「${row.question_text?.substring(0, 30)}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/quizzes/${row.quiz_id}/questions/${row.id}`)
    ElMessage.success('题目删除成功')
    loadQuestions(row.quiz_id)
  } catch {
    // cancelled or error
  }
}

// ---- Result Ranges ----
const loadRanges = async (quizId) => {
  try {
    const res = await request.get(`/quizzes/${quizId}/ranges`)
    const data = res?.items || res || []
    ranges.value = data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载结果区间失败')
    ranges.value = []
  }
}

const openRangeCreate = (quizId) => {
  currentQuizId.value = quizId
  rangeEditingId.value = null
  rangeForm.label = ''
  rangeForm.min_score = 0
  rangeForm.max_score = 100
  rangeForm.description = ''
  rangeForm.result_image = ''
  rangeDialogVisible.value = true
}

const openRangeEdit = (row) => {
  currentQuizId.value = row.quiz_id
  rangeEditingId.value = row.id
  rangeForm.label = row.label || ''
  rangeForm.min_score = row.min_score ?? 0
  rangeForm.max_score = row.max_score ?? 100
  rangeForm.description = row.description || ''
  rangeForm.result_image = row.result_image || ''
  rangeDialogVisible.value = true
}

const submitRange = async () => {
  if (!rangeForm.label.trim()) {
    ElMessage.warning('请输入区间标签')
    return
  }
  rangeFormLoading.value = true
  try {
    const payload = { ...rangeForm }
    if (rangeEditingId.value) {
      await request.put(`/quizzes/${currentQuizId.value}/ranges/${rangeEditingId.value}`, payload)
      ElMessage.success('区间更新成功')
    } else {
      await request.post(`/quizzes/${currentQuizId.value}/ranges`, payload)
      ElMessage.success('区间创建成功')
    }
    rangeDialogVisible.value = false
    loadRanges(currentQuizId.value)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存区间失败')
  } finally {
    rangeFormLoading.value = false
  }
}

const removeRange = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除区间「${row.label}」？`, '确认删除', { type: 'warning' })
    await request.delete(`/quizzes/${row.quiz_id}/ranges/${row.id}`)
    ElMessage.success('区间删除成功')
    loadRanges(row.quiz_id)
  } catch {
    // cancelled or error
  }
}

// Expand handler
const expandedRows = ref([])
const handleExpandChange = (row) => {
  if (expandedRows.value.includes(row.id)) {
    loadQuestions(row.id)
    loadRanges(row.id)
  }
}

onMounted(loadList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>问卷管理</h2>
      <el-button type="primary" @click="openCreate">新建问卷</el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe style="width: 100%"
      :expand-row-keys="expandedRows" @expand-change="handleExpandChange" row-key="id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-content">
            <el-tabs>
              <el-tab-pane label="题目管理">
                <div class="sub-header">
                  <el-button size="small" type="primary" @click="openQuestionCreate(row.id)">新增题目</el-button>
                </div>
                <el-table :data="questions" stripe size="small" style="width: 100%">
                  <el-table-column prop="id" label="ID" width="50" />
                  <el-table-column prop="question_text" label="题目内容" min-width="200" />
                  <el-table-column prop="question_type" label="类型" width="80" />
                  <el-table-column label="选项" min-width="150">
                    <template #default="{ row: q }">
                      <span class="options-preview">{{ q.options }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="sort_order" label="排序" width="60" />
                  <el-table-column label="操作" width="130">
                    <template #default="{ row: q }">
                      <el-button size="small" @click="openQuestionEdit(q)">编辑</el-button>
                      <el-button size="small" type="danger" @click="removeQuestion(q)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="结果区间管理">
                <div class="sub-header">
                  <el-button size="small" type="primary" @click="openRangeCreate(row.id)">新增区间</el-button>
                </div>
                <el-table :data="ranges" stripe size="small" style="width: 100%">
                  <el-table-column prop="id" label="ID" width="50" />
                  <el-table-column prop="label" label="标签" width="120" />
                  <el-table-column prop="min_score" label="最低分" width="80" />
                  <el-table-column prop="max_score" label="最高分" width="80" />
                  <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
                  <el-table-column label="操作" width="130">
                    <template #default="{ row: r }">
                      <el-button size="small" @click="openRangeEdit(r)">编辑</el-button>
                      <el-button size="small" type="danger" @click="removeRange(r)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.quiz_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="题目数" width="80" align="center">
        <template #default="{ row }">
          <span>{{ row.question_count ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="发布状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_published ? 'success' : 'info'" size="small">{{ row.is_published ? '已发布' : '草稿' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Quiz Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑问卷' : '新建问卷'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="问卷标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="问卷描述" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.quiz_type" style="width: 100%;">
            <el-option label="MBTI" value="mbti" />
            <el-option label="LGTI" value="lgti" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布">
          <el-switch v-model="form.is_published" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="submitQuiz">保存</el-button>
      </template>
    </el-dialog>

    <!-- Question Dialog -->
    <el-dialog v-model="questionDialogVisible" :title="questionEditingId ? '编辑题目' : '新增题目'" width="550px">
      <el-form :model="questionForm" label-width="100px">
        <el-form-item label="题目内容" required>
          <el-input v-model="questionForm.question_text" type="textarea" :rows="3" placeholder="题目内容" />
        </el-form-item>
        <el-form-item label="题目类型" required>
          <el-select v-model="questionForm.question_type" style="width: 100%;">
            <el-option label="选择题" value="choice" />
            <el-option label="判断题" value="true_false" />
            <el-option label="填空题" value="fill" />
          </el-select>
        </el-form-item>
        <el-form-item label="选项 JSON">
          <el-input v-model="questionForm.options" type="textarea" :rows="4" placeholder='[{"label":"A","value":"opt_a","score":1}]' />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="questionForm.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="questionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="questionFormLoading" @click="submitQuestion">保存</el-button>
      </template>
    </el-dialog>

    <!-- Range Dialog -->
    <el-dialog v-model="rangeDialogVisible" :title="rangeEditingId ? '编辑结果区间' : '新增结果区间'" width="550px">
      <el-form :model="rangeForm" label-width="100px">
        <el-form-item label="标签" required>
          <el-input v-model="rangeForm.label" placeholder="如：内向型、外向型" />
        </el-form-item>
        <el-form-item label="最低分">
          <el-input-number v-model="rangeForm.min_score" :min="0" />
        </el-form-item>
        <el-form-item label="最高分">
          <el-input-number v-model="rangeForm.max_score" :min="0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="rangeForm.description" type="textarea" :rows="3" placeholder="区间描述" />
        </el-form-item>
        <el-form-item label="结果图片">
          <el-input v-model="rangeForm.result_image" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rangeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rangeFormLoading" @click="submitRange">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.expand-content { padding: 12px 20px; }
.sub-header { margin-bottom: 10px; }
.options-preview { font-size: 12px; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; display: inline-block; }
</style>
