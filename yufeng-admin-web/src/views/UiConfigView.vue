<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Delete, Plus, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const saving = ref(false)

const bannerTemplate = () => ({
  id: `banner_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
  title: '',
  subtitle: '',
  image_url: '',
  target: '',
  enabled: true,
  sort_order: 0,
})

const featureTemplate = () => ({
  key: `feature_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
  title: '',
  description: '',
  icon: 'apps-o',
  color: 'blue',
  enabled: true,
  sort_order: 0,
})

const tabTemplate = () => ({
  key: `tab_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
  label: '',
  icon: 'apps-o',
  page_path: '/pages/activities/activities',
  enabled: true,
  sort_order: 0,
})

const tabbarTemplate = () => ({
  key: `tabbar_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
  label: '',
  icon: 'apps-o',
  page_path: '/pages/index/index',
  enabled: true,
  sort_order: 0,
})

const defaultConfig = () => ({
  home: {
    hero_title: '屿风活动报名',
    hero_subtitle: '发现真实、温暖、有质感的同城活动',
    hero_image: '',
    announcement: '欢迎来到屿风活动平台，报名后请留意审核与支付通知。',
    show_banner: true,
  },
  theme: {
    primary_color: '#7c3aed',
    accent_color: '#ec4899',
    text_color: '#111827',
    page_background: '#f8fafc',
    card_radius: 20,
  },
  contact: {
    service_wechat: 'JLGHTJ',
    service_phone: '13185500021',
    service_email: 'tangzengrong@yufengmedia.cn',
  },
  modules: {
    show_notice: true,
    show_banners: true,
    show_categories: true,
    show_contact: true,
    show_feature_labels: true,
    show_tabbar: true,
  },
  banners: [
    { id: 'banner_1', title: '推荐活动', subtitle: '优先展示官方精选活动', image_url: '', target: '推荐活动', enabled: true, sort_order: 1 },
    { id: 'banner_2', title: '周末搭子', subtitle: '适合周末快速组局', image_url: '', target: '周末搭子', enabled: true, sort_order: 2 },
  ],
  features: [
    { key: '运动', title: '运动', description: '组织跑步、健身、球类等更有男人味的线下相聚。', icon: 'medalfill', color: 'red', enabled: true, sort_order: 1 },
    { key: '旅行', title: '旅行', description: '周边短途、城市探索、节假日搭子局。', icon: 'locationfill', color: 'cyan', enabled: true, sort_order: 2 },
    { key: '音乐', title: '音乐', description: 'Livehouse、K歌、音乐节与共同聆听。', icon: 'musicfill', color: 'purple', enabled: true, sort_order: 3 },
    { key: '户外', title: '户外', description: '露营、徒步、飞盘和自然系社交。', icon: 'choicenessfill', color: 'green', enabled: true, sort_order: 4 },
  ],
  tabs: [
    { key: 'recommended', label: '推荐活动', icon: 'fire-o', page_path: '/pages/activities/activities', enabled: true, sort_order: 1 },
    { key: 'weekend', label: '周末搭子', icon: 'friends-o', page_path: '/pages/activities/activities', enabled: true, sort_order: 2 },
  ],
  tabbar: [
    { key: 'home', label: '首页', icon: 'wap-home-o', page_path: '/pages/index/index', enabled: true, sort_order: 1 },
    { key: 'my', label: '我的', icon: 'manager-o', page_path: '/pages/myactivity/myactivity', enabled: true, sort_order: 2 },
    { key: 'create', label: '创建', icon: 'add-o', page_path: '/pages/create_act/create_act', enabled: true, sort_order: 3 },
    { key: 'moments', label: '瞬间', icon: 'notes-o', page_path: '/pages/moments/moments', enabled: true, sort_order: 4 },
    { key: 'setting', label: '设置', icon: 'setting-o', page_path: '/pages/setting/setting', enabled: true, sort_order: 5 },
  ],
})

const iconOptions = [
  'apps-o', 'wap-home-o', 'manager-o', 'add-o', 'notes-o', 'setting-o', 'fire-o',
  'friends-o', 'new-o', 'medalfill', 'locationfill', 'musicfill', 'choicenessfill',
  'emojifill', 'camerafill', 'read', 'discoverfill', 'game', 'upstagefill', 'camera',
  'roundcheckfill', 'shop', 'creativefill', 'brandfill',
]

const colorOptions = ['red', 'orange', 'yellow', 'olive', 'green', 'cyan', 'blue', 'purple', 'mauve', 'pink', 'brown']
const colorMap = {
  red: '#E63946',
  orange: '#FF7A59',
  yellow: '#F4B400',
  olive: '#7CB342',
  green: '#34A853',
  cyan: '#00ACC1',
  blue: '#4285F4',
  purple: '#8E24AA',
  mauve: '#AB47BC',
  pink: '#EC4899',
  brown: '#8D6E63',
}

const form = reactive(defaultConfig())

function normalizeList(list, fallbackFactory, fieldMapper) {
  return Array.isArray(list) ? list.map((item, index) => fieldMapper(item || {}, index, fallbackFactory())).sort((a, b) => a.sort_order - b.sort_order) : []
}

function applyConfig(data) {
  const next = { ...defaultConfig(), ...(data || {}) }
  Object.assign(form.home, next.home || {})
  Object.assign(form.theme, next.theme || {})
  Object.assign(form.contact, next.contact || {})
  Object.assign(form.modules, next.modules || {})

  form.banners = normalizeList(next.banners, bannerTemplate, (item, index, fallback) => ({
    id: item.id || fallback.id,
    title: item.title || '',
    subtitle: item.subtitle || '',
    image_url: item.image_url || '',
    target: item.target || '',
    enabled: item.enabled !== false,
    sort_order: Number(item.sort_order ?? index + 1) || index + 1,
  }))

  form.features = normalizeList(next.features, featureTemplate, (item, index, fallback) => ({
    key: item.key || fallback.key,
    title: item.title || '',
    description: item.description || '',
    icon: item.icon || 'apps-o',
    color: item.color || 'blue',
    enabled: item.enabled !== false,
    sort_order: Number(item.sort_order ?? index + 1) || index + 1,
  }))

  form.tabs = normalizeList(next.tabs, tabTemplate, (item, index, fallback) => ({
    key: item.key || fallback.key,
    label: item.label || '',
    icon: item.icon || 'apps-o',
    page_path: item.page_path || '/pages/activities/activities',
    enabled: item.enabled !== false,
    sort_order: Number(item.sort_order ?? index + 1) || index + 1,
  }))

  form.tabbar = normalizeList(next.tabbar, tabbarTemplate, (item, index, fallback) => ({
    key: item.key || fallback.key,
    label: item.label || '',
    icon: item.icon || 'apps-o',
    page_path: item.page_path || '/pages/index/index',
    enabled: item.enabled !== false,
    sort_order: Number(item.sort_order ?? index + 1) || index + 1,
  }))
}

const loadConfig = async () => {
  loading.value = true
  try {
    const data = await request.get('/ui-config')
    applyConfig(data)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载UI配置失败')
  } finally {
    loading.value = false
  }
}

const serializeList = (list, requiredKeys = []) => list
  .map((item, index) => ({
    ...item,
    sort_order: Number(item.sort_order ?? index + 1) || index + 1,
  }))
  .filter(item => requiredKeys.every(key => String(item[key] || '').trim()))

const normalizePayload = () => ({
  home: { ...form.home },
  theme: {
    ...form.theme,
    card_radius: Number(form.theme.card_radius) || 0,
  },
  contact: { ...form.contact },
  modules: { ...form.modules },
  banners: serializeList(form.banners.map(item => ({
    id: (item.id || '').trim(),
    title: (item.title || '').trim(),
    subtitle: (item.subtitle || '').trim(),
    image_url: (item.image_url || '').trim(),
    target: (item.target || '').trim(),
    enabled: item.enabled !== false,
    sort_order: item.sort_order,
  })), ['id', 'title']),
  features: serializeList(form.features.map(item => ({
    key: (item.key || '').trim(),
    title: (item.title || '').trim(),
    description: (item.description || '').trim(),
    icon: (item.icon || 'apps-o').trim(),
    color: (item.color || 'blue').trim(),
    enabled: item.enabled !== false,
    sort_order: item.sort_order,
  })), ['key', 'title']),
  tabs: serializeList(form.tabs.map(item => ({
    key: (item.key || '').trim(),
    label: (item.label || '').trim(),
    icon: (item.icon || 'apps-o').trim(),
    page_path: (item.page_path || '').trim(),
    enabled: item.enabled !== false,
    sort_order: item.sort_order,
  })), ['key', 'label', 'page_path']),
  tabbar: serializeList(form.tabbar.map(item => ({
    key: (item.key || '').trim(),
    label: (item.label || '').trim(),
    icon: (item.icon || 'apps-o').trim(),
    page_path: (item.page_path || '').trim(),
    enabled: item.enabled !== false,
    sort_order: item.sort_order,
  })), ['key', 'label', 'page_path']),
})

const saveConfig = async () => {
  saving.value = true
  try {
    const data = await request.post('/ui-config', normalizePayload())
    applyConfig(data)
    ElMessage.success('UI配置已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存UI配置失败')
  } finally {
    saving.value = false
  }
}

const resetDefaults = () => {
  applyConfig(defaultConfig())
}

const addBanner = () => {
  form.banners.push({ ...bannerTemplate(), sort_order: form.banners.length + 1 })
}

const removeBanner = (index) => {
  form.banners.splice(index, 1)
}

const addFeature = () => {
  form.features.push({ ...featureTemplate(), sort_order: form.features.length + 1 })
}

const removeFeature = (index) => {
  form.features.splice(index, 1)
}

const addTab = () => {
  form.tabs.push({ ...tabTemplate(), sort_order: form.tabs.length + 1 })
}

const removeTab = (index) => {
  form.tabs.splice(index, 1)
}

const addTabbar = () => {
  form.tabbar.push({ ...tabbarTemplate(), sort_order: form.tabbar.length + 1 })
}

const removeTabbar = (index) => {
  form.tabbar.splice(index, 1)
}

const previewHeroStyle = computed(() => ({
  borderRadius: `${form.theme.card_radius}px`,
  backgroundImage: form.home.hero_image
    ? `linear-gradient(180deg, rgba(17,24,39,0.08), rgba(17,24,39,0.45)), url(${form.home.hero_image})`
    : `linear-gradient(135deg, ${form.theme.primary_color}, ${form.theme.accent_color})`,
  backgroundSize: 'cover',
  backgroundPosition: 'center',
}))

const previewPhoneStyle = computed(() => ({
  background: `linear-gradient(180deg, ${form.theme.page_background} 0%, #eef2ff 100%)`,
  color: form.theme.text_color,
}))

const previewNoticeStyle = computed(() => ({
  borderRadius: `${Math.max(12, form.theme.card_radius - 2)}px`,
}))

const enabledBanners = computed(() => [...form.banners].filter(item => item.enabled).sort((a, b) => a.sort_order - b.sort_order))
const enabledFeatures = computed(() => [...form.features].filter(item => item.enabled).sort((a, b) => a.sort_order - b.sort_order))
const enabledTabs = computed(() => [...form.tabs].filter(item => item.enabled).sort((a, b) => a.sort_order - b.sort_order))
const enabledTabbar = computed(() => [...form.tabbar].filter(item => item.enabled).sort((a, b) => a.sort_order - b.sort_order))

const previewBanners = computed(() => {
  const source = enabledBanners.value.length ? enabledBanners.value : defaultConfig().banners
  return source.slice(0, 3).map((item, index) => ({
    ...item,
    image_url: item.image_url || form.home.hero_image || `linear-gradient(135deg, ${form.theme.primary_color}, ${form.theme.accent_color})`,
    badge: enabledTabs.value[index]?.label || '推荐',
  }))
})

const previewFeatures = computed(() => {
  const source = enabledFeatures.value.length ? enabledFeatures.value : defaultConfig().features
  return source.slice(0, 8).map(item => ({
    ...item,
    colorHex: colorMap[item.color] || form.theme.primary_color,
  }))
})

const previewTabs = computed(() => enabledTabs.value.slice(0, 4))
const previewTabbar = computed(() => enabledTabbar.value.slice(0, 5))

onMounted(loadConfig)
</script>

<template>
  <div v-loading="loading" class="ui-config-page">
    <el-row :gutter="20">
      <el-col :span="15">
        <el-card class="page-card">
          <template #header>
            <div class="card-head">
              <strong>首页装修配置</strong>
              <el-button text type="primary" :icon="RefreshRight" @click="resetDefaults">恢复默认</el-button>
            </div>
          </template>
          <el-form label-width="110px">
            <el-form-item label="主标题">
              <el-input v-model="form.home.hero_title" maxlength="24" show-word-limit />
            </el-form-item>
            <el-form-item label="副标题">
              <el-input v-model="form.home.hero_subtitle" maxlength="40" show-word-limit />
            </el-form-item>
            <el-form-item label="Banner主图">
              <el-input v-model="form.home.hero_image" placeholder="顶部头图 URL，可为空" />
            </el-form-item>
            <el-form-item label="公告文案">
              <el-input v-model="form.home.announcement" type="textarea" :rows="3" maxlength="120" show-word-limit />
            </el-form-item>
            <el-form-item label="显示头图">
              <el-switch v-model="form.home.show_banner" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="page-card mt16">
          <template #header><strong>页面模块开关</strong></template>
          <div class="module-grid">
            <div class="module-item"><span>显示公告</span><el-switch v-model="form.modules.show_notice" /></div>
            <div class="module-item"><span>显示 Banner 轮播</span><el-switch v-model="form.modules.show_banners" /></div>
            <div class="module-item"><span>显示活动分类</span><el-switch v-model="form.modules.show_categories" /></div>
            <div class="module-item"><span>显示客服信息</span><el-switch v-model="form.modules.show_contact" /></div>
            <div class="module-item"><span>显示分类标题</span><el-switch v-model="form.modules.show_feature_labels" /></div>
            <div class="module-item"><span>显示底部 TabBar</span><el-switch v-model="form.modules.show_tabbar" /></div>
          </div>
        </el-card>

        <el-card class="page-card mt16">
          <template #header><strong>主题风格</strong></template>
          <div class="theme-grid">
            <el-form label-width="90px">
              <el-form-item label="主色">
                <div class="color-input-wrap">
                  <el-color-picker v-model="form.theme.primary_color" />
                  <el-input v-model="form.theme.primary_color" />
                </div>
              </el-form-item>
              <el-form-item label="强调色">
                <div class="color-input-wrap">
                  <el-color-picker v-model="form.theme.accent_color" />
                  <el-input v-model="form.theme.accent_color" />
                </div>
              </el-form-item>
              <el-form-item label="文字色">
                <div class="color-input-wrap">
                  <el-color-picker v-model="form.theme.text_color" />
                  <el-input v-model="form.theme.text_color" />
                </div>
              </el-form-item>
              <el-form-item label="背景色">
                <div class="color-input-wrap">
                  <el-color-picker v-model="form.theme.page_background" />
                  <el-input v-model="form.theme.page_background" />
                </div>
              </el-form-item>
              <el-form-item label="圆角">
                <el-slider v-model="form.theme.card_radius" :min="0" :max="40" show-input />
              </el-form-item>
            </el-form>
          </div>
        </el-card>

        <el-card class="page-card mt16">
          <template #header><strong>客服信息</strong></template>
          <el-form label-width="110px">
            <el-form-item label="客服微信">
              <el-input v-model="form.contact.service_wechat" />
            </el-form-item>
            <el-form-item label="客服电话">
              <el-input v-model="form.contact.service_phone" />
            </el-form-item>
            <el-form-item label="客服邮箱">
              <el-input v-model="form.contact.service_email" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="page-card mt16">
          <template #header>
            <div class="card-head">
              <strong>Banner 轮播管理</strong>
              <el-button type="primary" plain :icon="Plus" @click="addBanner">新增 Banner</el-button>
            </div>
          </template>
          <div class="list-editor">
            <div v-for="(item, index) in form.banners" :key="item.id + index" class="editor-item">
              <div class="editor-item-top">
                <span>Banner {{ index + 1 }}</span>
                <div class="editor-tools">
                  <el-switch v-model="item.enabled" active-text="显示" inactive-text="隐藏" />
                  <el-button text type="danger" :icon="Delete" @click="removeBanner(index)">删除</el-button>
                </div>
              </div>
              <el-row :gutter="12">
                <el-col :span="8"><el-input v-model="item.id" placeholder="唯一ID" /></el-col>
                <el-col :span="8"><el-input v-model="item.title" placeholder="标题" /></el-col>
                <el-col :span="8"><el-input-number v-model="item.sort_order" :min="1" :step="1" controls-position="right" class="full-width" /></el-col>
              </el-row>
              <el-input v-model="item.subtitle" class="mt12" placeholder="副标题" />
              <el-input v-model="item.image_url" class="mt12" placeholder="图片 URL" />
              <el-input v-model="item.target" class="mt12" placeholder="点击后传递的分类/目标，如 推荐活动" />
            </div>
          </div>
        </el-card>

        <el-card class="page-card mt16">
          <template #header>
            <div class="card-head">
              <strong>活动分类管理</strong>
              <el-button type="primary" plain :icon="Plus" @click="addFeature">新增分类</el-button>
            </div>
          </template>
          <div class="list-editor">
            <div v-for="(item, index) in form.features" :key="item.key + index" class="editor-item">
              <div class="editor-item-top">
                <span>分类 {{ index + 1 }}</span>
                <div class="editor-tools">
                  <el-switch v-model="item.enabled" active-text="显示" inactive-text="隐藏" />
                  <el-button text type="danger" :icon="Delete" @click="removeFeature(index)">删除</el-button>
                </div>
              </div>
              <el-row :gutter="12">
                <el-col :span="8"><el-input v-model="item.key" placeholder="key，如 运动" /></el-col>
                <el-col :span="8"><el-input v-model="item.title" placeholder="标题" /></el-col>
                <el-col :span="8"><el-input-number v-model="item.sort_order" :min="1" class="full-width" /></el-col>
              </el-row>
              <el-row :gutter="12" class="mt12">
                <el-col :span="12">
                  <el-select v-model="item.icon" class="full-width" placeholder="选择图标">
                    <el-option v-for="icon in iconOptions" :key="icon" :label="icon" :value="icon" />
                  </el-select>
                </el-col>
                <el-col :span="12">
                  <el-select v-model="item.color" class="full-width" placeholder="选择颜色">
                    <el-option v-for="color in colorOptions" :key="color" :label="color" :value="color" />
                  </el-select>
                </el-col>
              </el-row>
              <el-input v-model="item.description" type="textarea" :rows="2" class="mt12" placeholder="分类描述" />
            </div>
          </div>
        </el-card>

        <el-card class="page-card mt16">
          <template #header>
            <div class="card-head">
              <strong>首页导航标签</strong>
              <el-button type="primary" plain :icon="Plus" @click="addTab">新增标签</el-button>
            </div>
          </template>
          <div class="list-editor">
            <div v-for="(tab, index) in form.tabs" :key="tab.key + index" class="editor-item compact">
              <div class="editor-item-top">
                <span>标签 {{ index + 1 }}</span>
                <div class="editor-tools">
                  <el-switch v-model="tab.enabled" active-text="显示" inactive-text="隐藏" />
                  <el-button text type="danger" :icon="Delete" @click="removeTab(index)">删除</el-button>
                </div>
              </div>
              <el-row :gutter="12">
                <el-col :span="6"><el-input v-model="tab.key" placeholder="key" /></el-col>
                <el-col :span="6"><el-input v-model="tab.label" placeholder="文案" /></el-col>
                <el-col :span="6">
                  <el-select v-model="tab.icon" class="full-width" placeholder="图标">
                    <el-option v-for="icon in iconOptions" :key="icon" :label="icon" :value="icon" />
                  </el-select>
                </el-col>
                <el-col :span="6"><el-input-number v-model="tab.sort_order" :min="1" class="full-width" /></el-col>
              </el-row>
              <el-input v-model="tab.page_path" class="mt12" placeholder="跳转页面，如 /pages/activities/activities" />
            </div>
          </div>
        </el-card>

        <el-card class="page-card mt16">
          <template #header>
            <div class="card-head">
              <strong>底部 TabBar 配置</strong>
              <el-button type="primary" plain :icon="Plus" @click="addTabbar">新增底栏项</el-button>
            </div>
          </template>
          <div class="list-editor">
            <div v-for="(tab, index) in form.tabbar" :key="tab.key + index" class="editor-item compact">
              <div class="editor-item-top">
                <span>底栏项 {{ index + 1 }}</span>
                <div class="editor-tools">
                  <el-switch v-model="tab.enabled" active-text="显示" inactive-text="隐藏" />
                  <el-button text type="danger" :icon="Delete" @click="removeTabbar(index)">删除</el-button>
                </div>
              </div>
              <el-row :gutter="12">
                <el-col :span="6"><el-input v-model="tab.key" placeholder="key" /></el-col>
                <el-col :span="6"><el-input v-model="tab.label" placeholder="文案" /></el-col>
                <el-col :span="6">
                  <el-select v-model="tab.icon" class="full-width" placeholder="图标">
                    <el-option v-for="icon in iconOptions" :key="icon" :label="icon" :value="icon" />
                  </el-select>
                </el-col>
                <el-col :span="6"><el-input-number v-model="tab.sort_order" :min="1" class="full-width" /></el-col>
              </el-row>
              <el-input v-model="tab.page_path" class="mt12" placeholder="页面路径，如 /pages/index/index" />
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="9">
        <el-card class="page-card preview-card">
          <template #header>
            <div class="card-head">
              <strong>实时预览</strong>
              <span class="preview-tip">接近小程序首页真机画面</span>
            </div>
          </template>

          <div class="preview-device-wrap">
            <div class="preview-device">
              <div class="preview-device-notch"></div>
              <div class="preview-screen" :style="previewPhoneStyle">
                <div class="preview-status-bar">
                  <span>9:41</span>
                  <span>5G · 100%</span>
                </div>

                <div class="preview-navbar">屿风活动</div>

                <div class="preview-scroll">
                  <div v-if="form.home.show_banner" class="preview-hero" :style="previewHeroStyle">
                    <div class="preview-avatar">屿</div>
                    <div class="preview-hero-texts">
                      <div class="preview-title">{{ form.home.hero_title || '屿风活动报名' }}</div>
                      <div class="preview-subtitle">{{ form.home.hero_subtitle || '发现真实、温暖、有质感的同城活动' }}</div>
                    </div>
                  </div>

                  <div v-if="form.modules.show_notice && form.home.announcement" class="preview-notice" :style="previewNoticeStyle">
                    <span class="preview-notice-badge">公告</span>
                    <span>{{ form.home.announcement }}</span>
                  </div>

                  <template v-if="form.modules.show_banners">
                    <div class="preview-card-swiper">
                      <div
                        v-for="item in previewBanners"
                        :key="item.id"
                        class="preview-swiper-item"
                        :style="{
                          backgroundImage: item.image_url.startsWith('linear-gradient')
                            ? item.image_url
                            : `linear-gradient(180deg, rgba(0,0,0,0.08), rgba(0,0,0,0.45)), url(${item.image_url})`
                        }"
                      >
                        <div class="preview-swiper-badge">{{ item.badge }}</div>
                        <div class="preview-swiper-title">{{ item.title || '未命名 Banner' }}</div>
                        <div class="preview-swiper-subtitle">{{ item.subtitle || '等待补充副标题' }}</div>
                      </div>
                    </div>
                  </template>

                  <div v-if="form.modules.show_categories && form.modules.show_feature_labels" class="preview-section-title">
                    <span class="preview-section-line"></span>
                    <span>活动分类</span>
                    <span class="preview-section-line"></span>
                  </div>

                  <div v-if="form.modules.show_categories" class="preview-feature-grid">
                    <div v-for="item in previewFeatures" :key="item.key" class="preview-feature-item">
                      <div class="preview-feature-icon" :style="{ color: item.colorHex }">
                        {{ (item.title || item.key || '类').slice(0, 1) }}
                      </div>
                      <div class="preview-feature-name">{{ item.title || '未命名分类' }}</div>
                    </div>
                  </div>

                  <div v-if="previewTabs.length" class="preview-tab-strip">
                    <span v-for="(tab, index) in previewTabs" :key="tab.key" class="preview-chip" :class="{ active: index === 0 }">
                      {{ tab.label || '未命名标签' }}
                    </span>
                  </div>

                  <div class="preview-content-card">
                    <div class="preview-content-title">{{ previewTabs[0]?.label || '推荐活动' }}</div>
                    <div class="preview-content-desc">这里将展示对应标签下的活动流，当前预览重点是装修样式与结构。</div>
                  </div>

                  <div v-if="form.modules.show_contact && (form.contact.service_wechat || form.contact.service_phone || form.contact.service_email)" class="preview-contact-card">
                    <div class="preview-contact-title">联系屿风</div>
                    <div v-if="form.contact.service_wechat" class="preview-contact-item">客服微信：{{ form.contact.service_wechat }}</div>
                    <div v-if="form.contact.service_phone" class="preview-contact-item">客服电话：{{ form.contact.service_phone }}</div>
                    <div v-if="form.contact.service_email" class="preview-contact-item">客服邮箱：{{ form.contact.service_email }}</div>
                  </div>
                </div>

                <div v-if="form.modules.show_tabbar" class="preview-tabbar">
                  <div v-for="(tab, index) in previewTabbar" :key="tab.key" class="preview-tabbar-item" :class="{ active: index === 0 }">
                    <div class="preview-tabbar-icon">{{ (tab.label || '导').slice(0, 1) }}</div>
                    <div class="preview-tabbar-text">{{ tab.label || '未命名' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="actions">
            <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.ui-config-page { min-height: 100%; }
.mt12 { margin-top: 12px; }
.mt16 { margin-top: 16px; }
.full-width { width: 100%; }
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.preview-tip {
  color: #6b7280;
  font-size: 12px;
}
.theme-grid {
  display: grid;
  grid-template-columns: 1fr;
}
.module-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.module-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fafafa;
}
.color-input-wrap {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 10px;
  align-items: center;
}
.list-editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.editor-item {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 16px;
  background: #fafafa;
}
.editor-item.compact {
  background: #fff;
}
.editor-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}
.editor-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}
.preview-card { position: sticky; top: 24px; }
.preview-device-wrap {
  display: flex;
  justify-content: center;
  padding: 8px 0 4px;
}
.preview-device {
  width: 360px;
  height: 760px;
  border-radius: 36px;
  padding: 12px;
  background: linear-gradient(180deg, #1f2937, #111827);
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.28);
  position: relative;
}
.preview-device-notch {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  width: 120px;
  height: 18px;
  border-radius: 999px;
  background: #0b1220;
  z-index: 5;
}
.preview-screen {
  height: 100%;
  border-radius: 28px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255,255,255,0.08);
}
.preview-status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 18px 8px;
  font-size: 12px;
  color: #0f172a;
}
.preview-navbar {
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  padding: 4px 18px 14px;
}
.preview-scroll {
  flex: 1;
  overflow: auto;
  padding: 0 16px 16px;
}
.preview-hero {
  min-height: 126px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  color: #fff;
  box-shadow: 0 10px 30px rgba(17, 24, 39, 0.14);
}
.preview-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255,255,255,0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  border: 2px solid rgba(255,255,255,0.5);
  flex-shrink: 0;
}
.preview-hero-texts {
  min-width: 0;
}
.preview-title {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}
.preview-subtitle {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  opacity: 0.92;
}
.preview-notice {
  margin-top: 14px;
  background: rgba(255,255,255,0.82);
  padding: 12px 14px;
  line-height: 1.7;
  font-size: 13px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}
.preview-notice-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  margin-right: 10px;
  color: #fff;
  font-size: 12px;
  background: linear-gradient(135deg, v-bind('form.theme.primary_color'), v-bind('form.theme.accent_color'));
}
.preview-card-swiper {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-top: 16px;
}
.preview-swiper-item {
  min-height: 140px;
  border-radius: 20px;
  padding: 16px;
  color: #fff;
  background-size: cover;
  background-position: center;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  box-shadow: 0 12px 28px rgba(17, 24, 39, 0.16);
}
.preview-swiper-badge {
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(255,255,255,0.2);
  backdrop-filter: blur(8px);
  margin-bottom: 10px;
}
.preview-swiper-title {
  font-size: 20px;
  font-weight: 700;
}
.preview-swiper-subtitle {
  font-size: 12px;
  opacity: 0.92;
  margin-top: 6px;
}
.preview-section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 18px 0 12px;
  font-size: 15px;
  font-weight: 700;
}
.preview-section-line {
  width: 36px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, v-bind('form.theme.primary_color'), v-bind('form.theme.accent_color'));
}
.preview-feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px 8px;
  margin-top: 6px;
}
.preview-feature-item {
  text-align: center;
}
.preview-feature-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 8px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}
.preview-feature-name {
  font-size: 12px;
  font-weight: 500;
}
.preview-tab-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}
.preview-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.9);
  border: 1px solid #e5e7eb;
  font-size: 12px;
  color: #475569;
}
.preview-chip.active {
  color: #fff;
  border-color: transparent;
  background: linear-gradient(135deg, v-bind('form.theme.primary_color'), v-bind('form.theme.accent_color'));
}
.preview-content-card,
.preview-contact-card {
  margin-top: 16px;
  background: rgba(255,255,255,0.96);
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}
.preview-content-title,
.preview-contact-title {
  font-size: 15px;
  font-weight: 700;
}
.preview-content-desc,
.preview-contact-item {
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}
.preview-tabbar {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 4px;
  padding: 10px 10px 12px;
  background: rgba(255,255,255,0.96);
  border-top: 1px solid #e5e7eb;
}
.preview-tabbar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #94a3b8;
  min-height: 48px;
}
.preview-tabbar-item.active {
  color: v-bind('form.theme.accent_color');
}
.preview-tabbar-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  background: currentColor;
  color: #fff;
}
.preview-tabbar-text {
  font-size: 11px;
}
.actions { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
