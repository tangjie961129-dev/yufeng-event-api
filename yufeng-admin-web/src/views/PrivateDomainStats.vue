<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const loading = ref(false)
const data = ref(null)

const money = (v) => `¥${Number(v || 0).toFixed(2)}`
const pct = (v, total) => total > 0 ? ((v / total) * 100).toFixed(1) : '0.0'

const loadStats = async () => {
  loading.value = true
  try {
    const res = await request.get('/admin/stats/private-domain', { params: { days: 30 } })
    data.value = res
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载统计数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<template>
  <div class="stats-page" v-loading="loading">
    <div class="page-header">
      <h2>📊 私域数据统计</h2>
      <el-button type="primary" size="small" @click="loadStats" :loading="loading">刷新</el-button>
    </div>

    <template v-if="data">
      <!-- 概览卡片 -->
      <div class="overview-cards">
        <div class="card card-accent">
          <div class="card-label">渠道主</div>
          <div class="card-value">{{ data.overview.total_partners }}</div>
          <div class="card-sub">活跃 {{ data.overview.active_partners }} / 今日新增 {{ data.overview.new_partners_today }}</div>
        </div>
        <div class="card card-blue">
          <div class="card-label">填表数</div>
          <div class="card-value">{{ data.overview.total_registers }}</div>
          <div class="card-sub">今日 {{ data.overview.today_registers }} / 昨日 {{ data.overview.yesterday_registers }}</div>
        </div>
        <div class="card card-green">
          <div class="card-label">总佣金</div>
          <div class="card-value">{{ money(data.overview.total_commission) }}</div>
          <div class="card-sub">可提现 {{ money(data.overview.total_withdrawable) }}</div>
        </div>
        <div class="card card-orange">
          <div class="card-label">今日佣金</div>
          <div class="card-value">{{ money(data.overview.today_commission) }}</div>
          <div class="card-sub">昨日 {{ money(data.overview.yesterday_commission) }}</div>
        </div>
        <div class="card card-purple">
          <div class="card-label">引流点击</div>
          <div class="card-value">{{ data.overview.total_clicks }}</div>
          <div class="card-sub">今日 {{ data.overview.today_clicks }}</div>
        </div>
      </div>

      <!-- 每日趋势 + 渠道排行 两栏 -->
      <div class="two-col">
        <!-- 渠道主排行 -->
        <div class="section-card">
          <h3>🏆 渠道主排行</h3>
          <el-table :data="data.partner_ranking" size="small" stripe style="width:100%" v-if="data.partner_ranking.length">
            <el-table-column label="渠道主" min-width="120">
              <template #default="{ row }">
                <strong>{{ row.name }}</strong>
                <el-tag size="small" style="margin-left:4px">{{ row.source }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="registers" label="填表" width="60" />
            <el-table-column prop="deals" label="成交" width="60" />
            <el-table-column label="佣金" width="100">
              <template #default="{ row }">{{ money(row.commission) }}</template>
            </el-table-column>
            <el-table-column label="可提现" width="100">
              <template #default="{ row }">{{ money(row.withdrawable) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无渠道主数据" />
        </div>

        <!-- 渠道引流 -->
        <div class="section-card">
          <h3>📡 引流渠道分布</h3>
          <el-table :data="data.channel_breakdown" size="small" stripe style="width:100%" v-if="data.channel_breakdown.length">
            <el-table-column label="渠道" min-width="100">
              <template #default="{ row }">
                <strong>{{ row.name }}</strong>
                <el-tag size="small" type="info" style="margin-left:4px">{{ row.channel }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total" label="点击" width="70" />
            <el-table-column prop="unique_ips" label="独立IP" width="80" />
          </el-table>
          <el-empty v-else description="暂无引流数据" />
        </div>
      </div>

      <!-- 每日趋势 -->
      <div class="section-card">
        <h3>📈 每日趋势（近{{ data.days }}天）</h3>
        <div class="trend-chart" v-if="data.daily_trend.length">
          <div class="trend-bar" v-for="item in data.daily_trend" :key="item.day">
            <div class="trend-bar-fill" :style="{ height: pct(item.registers, Math.max(...data.daily_trend.map(d=>d.registers),1)) + '%' }">
              <span class="trend-val">{{ item.registers }}</span>
            </div>
            <div class="trend-label">{{ item.day.slice(5) }}</div>
            <div class="trend-commission">{{ money(item.commission) }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无趋势数据" />
      </div>

      <!-- 最近填表记录 -->
      <div class="section-card">
        <h3>🕐 最近填表记录</h3>
        <el-table :data="data.recent_activity" size="small" stripe style="width:100%" v-if="data.recent_activity.length">
          <el-table-column label="客户" prop="customer" width="100" />
          <el-table-column label="渠道主" prop="partner" width="120" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'confirmed' ? 'success' : 'warning'" size="small">
                {{ row.status === 'confirmed' ? '已确认' : row.status === 'pending' ? '待确认' : row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="佣金" width="80">
            <template #default="{ row }">{{ money(row.fee) }}</template>
          </el-table-column>
          <el-table-column label="时间" prop="date" min-width="140" />
        </el-table>
        <el-empty v-else description="暂无填表记录" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-page {
  padding: 20px;
  color: #e0e0e0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #e94560;
}
.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.card {
  background: #16213e;
  border-radius: 14px;
  padding: 18px 20px;
  border: 1px solid #233554;
}
.card-accent { border-left: 3px solid #e94560; }
.card-blue { border-left: 3px solid #4fc3f7; }
.card-green { border-left: 3px solid #64ffda; }
.card-orange { border-left: 3px solid #ffa726; }
.card-purple { border-left: 3px solid #ce93d8; }
.card-label {
  font-size: 12px;
  color: #8892b0;
  margin-bottom: 6px;
}
.card-value {
  font-size: 26px;
  font-weight: 700;
}
.card-accent .card-value { color: #e94560; }
.card-blue .card-value { color: #4fc3f7; }
.card-green .card-value { color: #64ffda; }
.card-orange .card-value { color: #ffa726; }
.card-purple .card-value { color: #ce93d8; }
.card-sub {
  font-size: 11px;
  color: #5a6a8a;
  margin-top: 4px;
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.section-card {
  background: #16213e;
  border-radius: 14px;
  padding: 18px 20px;
  border: 1px solid #233554;
  margin-bottom: 20px;
}
.section-card h3 {
  margin: 0 0 14px 0;
  font-size: 15px;
  color: #e0e0e0;
}
.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 160px;
  padding: 10px 0;
  overflow-x: auto;
}
.trend-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 36px;
  flex-shrink: 0;
}
.trend-bar-fill {
  width: 24px;
  background: linear-gradient(to top, #e94560, #ff6b81);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  position: relative;
  display: flex;
  justify-content: center;
  transition: height 0.3s;
}
.trend-val {
  position: absolute;
  top: -18px;
  font-size: 11px;
  color: #e0e0e0;
  white-space: nowrap;
}
.trend-label {
  font-size: 10px;
  color: #5a6a8a;
  margin-top: 4px;
}
.trend-commission {
  font-size: 9px;
  color: #64ffda;
  margin-top: 2px;
}
</style>
