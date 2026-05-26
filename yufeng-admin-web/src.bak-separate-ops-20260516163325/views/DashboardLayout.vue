<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { DataBoard, User, Tickets, Checked, Brush, Lock, UserFilled, Coin, Wallet, Setting, Collection, Picture, Grid, Bell, Reading, Document, Link, MagicStick, PriceTag, Expand, Fold, Connection } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const sidebarOpen = ref(false)

const menus = [
  { label: '仪表盘', path: '/dashboard', icon: DataBoard },
  { label: 'UI装修', path: '/ui-config', icon: Brush },
  { label: '分类管理', path: '/cms/categories', icon: Collection },
  { label: 'Banner管理', path: '/cms/banners', icon: Picture },
  { label: '页面组件', path: '/cms/widgets', icon: Grid },
  { label: '公告管理', path: '/cms/announcements', icon: Bell },
  { label: '课程管理', path: '/courses', icon: Reading },
  { label: '问卷管理', path: '/quizzes', icon: Document },
  { label: '匹配记录', path: '/love/matches', icon: Link },
  { label: 'AI男友管理', path: '/love/boyfriend', icon: MagicStick },
  { label: '会员标签', path: '/member-tags', icon: PriceTag },
  { label: '企微回补', path: '/wecom-backfill', icon: Connection },
  { label: '主办方审核', path: '/certifications', icon: Checked },
  { label: '活动审核', path: '/events', icon: Tickets },
  { label: '订单台账', path: '/orders', icon: DataBoard },
  { label: '报名管理', path: '/registrations', icon: Tickets },
  { label: '用户管理', path: '/users', icon: User },
  { label: '权限与后台账号', path: '/permissions', icon: Lock },
  { label: '分销员管理', path: '/distributors', icon: UserFilled },
  { label: '合伙人体系', path: '/partners', icon: UserFilled },
  { label: '佣金台账', path: '/commissions', icon: Coin },
  { label: '提现审核', path: '/withdrawals', icon: Wallet },
  { label: '管理员管理', path: '/admins', icon: Setting },
]

const activeMenu = computed(() => route.path)

const logout = () => {
  authStore.logout()
  router.push('/login')
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

function navigateTo(path) {
  router.push(path)
  sidebarOpen.value = false
}
</script>

<template>
  <div class="layout-shell">
    <!-- 手机侧边栏遮罩 -->
    <div class="sidebar-overlay" v-show="sidebarOpen" @click="sidebarOpen = false"></div>

    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ 'sidebar-open': sidebarOpen }">
      <div class="brand">
        <span>🌈</span> 屿风 Admin
      </div>
      <el-menu :default-active="activeMenu" router background-color="transparent" text-color="#cbd5e1" active-text-color="#fff" @select="(i) => sidebarOpen = false">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <el-button class="menu-btn" @click="toggleSidebar" text>
            <el-icon :size="22"><Expand v-if="!sidebarOpen" /><Fold v-else /></el-icon>
          </el-button>
          <div>
            <div class="top-title">屿风活动运营后台</div>
            <div class="top-desc">审核、订单、用户、页面装修、权限与分销统一管理</div>
          </div>
        </div>
        <div class="top-actions">
          <span class="admin-name">{{ authStore.user?.display_name || '管理员' }}</span>
          <el-button @click="logout" size="small" round>退出登录</el-button>
        </div>
      </header>
      <main class="content-wrap">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout-shell { display: flex; min-height: 100vh; }
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #0f172a, #111827);
  padding: 24px 16px;
  transition: transform .25s ease;
  z-index: 100;
}
.brand {
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.menu-btn { display: none; }
.topbar {
  min-height: 84px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.topbar-left { display: flex; align-items: center; gap: 12px; }
.top-title { font-size: 24px; font-weight: 700; color: #111827; }
.top-desc { color: #6b7280; margin-top: 4px; font-size: 14px; }
.top-actions { display: flex; align-items: center; gap: 12px; }
.admin-name { color: #374151; font-weight: 600; }
.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.content-wrap { padding: 24px; flex: 1; }
.sidebar-overlay { display: none; }

@media(max-width: 767px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transform: translateX(-100%);
    padding: 16px 12px;
  }
  .sidebar.sidebar-open { transform: translateX(0); }
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.35);
    z-index: 99;
  }
  .menu-btn { display: inline-flex; }
  .top-title { font-size: 18px; }
  .top-desc { display: none; }
  .topbar { padding: 0 12px; min-height: 60px; }
  .content-wrap { padding: 12px; }
  .top-actions .admin-name { display: none; }
}
</style>
