<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const forms = ref([])
const selectedFormSlug = ref('')
const channels = ref([])
const stats = ref([])
const creating = ref(false)
const creatingQr = ref({})
const latestLink = ref(null)
const latestLinkRef = ref(null)

const newChannel = ref({
  name: '',
  promoter_name: '',
  promoter_type: 'employee',
  employee_userid: '',
  source: '朋友圈',
  code: '',
  note: '',
  create_wecom_contact_way: false,
})

const selectedForm = computed(() => forms.value.find((item) => item.slug === selectedFormSlug.value))

const sourceOptions = ['朋友圈', '微信群', '个人微信', '小红书', '公众号', '线下活动', '员工转发', '其他']
const typeOptions = [
  { label: '员工/客服', value: 'employee' },
  { label: 'KOC/朋友', value: 'koc' },
  { label: '渠道号', value: 'channel' },
  { label: '广告投放', value: 'ad' },
]

const loadForms = async () => {
  const res = await request.get('/lead-forms')
  forms.value = res || []
  if (!selectedFormSlug.value && forms.value.length) selectedFormSlug.value = forms.value[0].slug
}

const loadAttribution = async () => {
  if (!selectedFormSlug.value) return
  loading.value = true
  try {
    const [channelRows, statRows] = await Promise.all([
      request.get('/lead-forms/channels', { params: { form_slug: selectedFormSlug.value } }),
      request.get('/lead-forms/attribution/summary', { params: { form_slug: selectedFormSlug.value } }),
    ])
    channels.value = channelRows || []
    stats.value = statRows || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载归因统计失败')
  } finally {
    loading.value = false
  }
}

const refreshAll = async () => {
  await loadForms()
  await loadAttribution()
}

const absUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `${window.location.origin}${url}`
}

const copyText = async (text, label = '内容') => {
  if (!text) return
  await navigator.clipboard.writeText(text)
  ElMessage.success(`${label}已复制`)
}

const createChannel = async () => {
  latestLink.value = null
  if (!selectedFormSlug.value) return ElMessage.warning('请先选择表单')
  if (!newChannel.value.name.trim()) return ElMessage.warning('请填写渠道名称')
  creating.value = true
  try {
    const row = await request.post('/lead-forms/channels', { ...newChannel.value, form_slug: selectedFormSlug.value })
    latestLink.value = { ...row, created_at: new Date().toISOString() }
    ElMessage.success('渠道链接已生成，已显示在下方')
    await copyText(row.url, '渠道链接')
    newChannel.value = { name: '', promoter_name: '', promoter_type: 'employee', employee_userid: '', source: '朋友圈', code: '', note: '', create_wecom_contact_way: false }
    await loadAttribution()
    await nextTick()
    latestLinkRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建渠道失败')
  } finally {
    creating.value = false
  }
}

const createContactWay = async (row) => {
  if (!row?.id) return
  if (!row.employee_userid) return ElMessage.warning('该渠道缺少企微员工ID')
  creatingQr.value[row.id] = true
  try {
    const updated = await request.post(`/lead-forms/channels/${row.id}/contact-way`)
    const patchRow = (item) => (item.id === updated.id ? { ...item, ...updated } : item)
    channels.value = channels.value.map(patchRow)
    stats.value = stats.value.map((item) => item.channel_id === updated.id ? { ...item, ...updated } : item)
    ElMessage.success('企微联系我二维码已创建')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建企微二维码失败')
  } finally {
    creatingQr.value[row.id] = false
  }
}

const getStats = (code) => stats.value.find((item) => item.channel_code === code) || {}

onMounted(refreshAll)
</script>

<template>
  <div class="attribution-page" v-loading="loading">
    <div class="page-head">
      <div>
        <p class="eyebrow">Attribution</p>
        <h1>引流归因统计</h1>
        <p>给不同员工、朋友、渠道生成不同链接，统计访问、填表和加企微数量。</p>
      </div>
      <div class="head-actions">
        <el-select v-model="selectedFormSlug" placeholder="选择表单" style="width: 240px" @change="loadAttribution">
          <el-option v-for="form in forms" :key="form.slug" :label="`${form.name} / ${form.slug}`" :value="form.slug" />
        </el-select>
        <el-button @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <template #header><strong>生成渠道链接</strong></template>
      <div class="create-grid">
        <el-form-item label="渠道名称"><el-input v-model="newChannel.name" placeholder="如：张三朋友圈 / 小红书达人A" /></el-form-item>
        <el-form-item label="推广人"><el-input v-model="newChannel.promoter_name" placeholder="谁负责发" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="newChannel.promoter_type"><el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="来源"><el-select v-model="newChannel.source" filterable allow-create><el-option v-for="item in sourceOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item>
        <el-form-item label="企微员工ID"><el-input v-model="newChannel.employee_userid" placeholder="可选，用于专属员工归因" /></el-form-item>
        <el-form-item label="自定义编码"><el-input v-model="newChannel.code" placeholder="可选，如 zhangsan-friend" /></el-form-item>
        <el-form-item label="企微二维码"><el-switch v-model="newChannel.create_wecom_contact_way" active-text="同时创建" inactive-text="稍后创建" /></el-form-item>
      </div>
      <el-form-item label="备注"><el-input v-model="newChannel.note" type="textarea" :rows="2" /></el-form-item>
      <div class="create-actions">
        <el-button type="primary" :loading="creating" @click="createChannel">生成并复制渠道链接</el-button>
        <span class="muted">勾选“同时创建”时会调用企微客户联系接口，生成带 state=yfch_渠道编码 的联系我二维码。</span>
      </div>
      <div v-if="latestLink" ref="latestLinkRef" class="latest-link-card">
        <div class="latest-link-title">刚生成的链接</div>
        <div class="latest-link-name">{{ latestLink.name }} · 渠道编码 {{ latestLink.code }}</div>
        <div class="latest-link-row">
          <el-input :model-value="latestLink.url" readonly />
          <el-button type="primary" plain @click="copyText(latestLink.url, '渠道链接')">复制链接</el-button>
          <el-button @click="window.open(latestLink.url, '_blank')">打开</el-button>
        </div>
        <div v-if="latestLink.wecom_qr_code_url" class="qr-preview">
          <img :src="absUrl(latestLink.wecom_qr_code_url)" alt="企微联系我二维码" />
          <div>
            <strong>企微联系我二维码已生成</strong>
            <div class="muted">state：{{ latestLink.wecom_state }}</div>
            <el-button size="small" @click="copyText(absUrl(latestLink.wecom_qr_code_url), '二维码图片地址')">复制二维码地址</el-button>
          </div>
        </div>
        <div class="muted">这条链接也已加入下面的“渠道数据”表格，后续访问/填表会自动计入该渠道。</div>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header"><strong>渠道数据</strong><span>{{ selectedForm?.name || selectedFormSlug }}</span></div>
      </template>
      <el-table :data="channels" stripe>
        <el-table-column label="渠道" min-width="180">
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
            <div class="muted">{{ row.promoter_name || '-' }} · {{ row.source || '-' }}</div>
            <div class="muted">{{ row.code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="访问" width="90">
          <template #default="{ row }">{{ getStats(row.code).views || 0 }}</template>
        </el-table-column>
        <el-table-column label="填表" width="90">
          <template #default="{ row }">{{ getStats(row.code).submits || 0 }}</template>
        </el-table-column>
        <el-table-column label="加企微" width="90">
          <template #default="{ row }">{{ getStats(row.code).wecom_adds || 0 }}</template>
        </el-table-column>
        <el-table-column label="填表率" width="100">
          <template #default="{ row }">{{ getStats(row.code).submit_rate || 0 }}%</template>
        </el-table-column>
        <el-table-column label="加企微率" width="110">
          <template #default="{ row }">{{ getStats(row.code).wecom_add_rate || 0 }}%</template>
        </el-table-column>
        <el-table-column label="链接" min-width="320">
          <template #default="{ row }">
            <div class="link-row">
              <el-input :model-value="row.url" readonly size="small" />
              <el-button size="small" @click="copyText(row.url, '渠道链接')">复制</el-button>
              <el-button size="small" @click="window.open(row.url, '_blank')">打开</el-button>
            </div>
            <div class="muted">企微渠道二维码 state：{{ row.wecom_state || ('yfch_' + row.code) }}</div>
            <div v-if="row.wecom_qr_code_url" class="table-qr-row">
              <img :src="absUrl(row.wecom_qr_code_url)" alt="企微二维码" />
              <el-button size="small" @click="copyText(absUrl(row.wecom_qr_code_url), '二维码图片地址')">复制二维码</el-button>
              <el-button size="small" @click="window.open(absUrl(row.wecom_qr_code_url), '_blank')">打开二维码</el-button>
            </div>
            <el-button v-else size="small" type="success" plain :loading="creatingQr[row.id]" @click="createContactWay(row)">创建企微联系我二维码</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="tip">“加企微”只有在企微客户添加事件带有 state=yfch_渠道编码 时能自动统计；普通扫码直接加个人微信无法被企微 API 回传。</p>
    </el-card>
  </div>
</template>

<style scoped>
.attribution-page { display: flex; flex-direction: column; gap: 18px; }
.page-head { background: linear-gradient(135deg, #7c3aed, #0f766e); color: #fff; border-radius: 22px; padding: 24px; display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.page-head h1 { margin: 4px 0 8px; font-size: 28px; }
.page-head p { margin: 0; opacity: .9; }
.eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; opacity: .75 !important; }
.head-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.create-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.card-header { display:flex; justify-content:space-between; align-items:center; }
.card-header span, .muted { color:#64748b; font-size:12px; }
.create-actions { margin-top: 4px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.link-row, .latest-link-row { display:grid; grid-template-columns: 1fr auto auto; gap:8px; align-items:center; }
.latest-link-card { margin-top: 16px; padding: 14px; border: 1px solid #bfdbfe; background: linear-gradient(135deg, #eff6ff, #f0fdfa); border-radius: 14px; }
.latest-link-title { font-weight: 800; color: #1d4ed8; margin-bottom: 4px; }
.latest-link-name { font-size: 13px; color: #334155; margin-bottom: 10px; }
.qr-preview { margin-top: 12px; display:flex; gap:12px; align-items:center; }
.qr-preview img { width:96px; height:96px; object-fit:cover; border-radius:10px; border:1px solid #dbeafe; background:#fff; }
.table-qr-row { display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; }
.table-qr-row img { width:54px; height:54px; object-fit:cover; border-radius:8px; border:1px solid #e2e8f0; }
.tip { color:#8b6f3c; font-size:13px; margin:12px 0 0; }
@media (max-width: 900px) { .page-head, .create-grid, .link-row, .latest-link-row { display:flex; flex-direction:column; align-items:stretch; } }
</style>
