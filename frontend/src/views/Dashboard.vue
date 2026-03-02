<template>
  <div class="dashboard">
    <el-row :gutter="16" class="stat-row">
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="采集用户总数" :value="stats.total_users" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="采集任务数" :value="stats.total_tasks" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="触达记录数" :value="stats.total_touches" />
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-top: 16px">
      <template #header>数据趋势（待接入）</template>
      <div ref="chartRef" style="height: 300px"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '../api/http'
import * as echarts from 'echarts'

const stats = ref({ total_users: 0, total_tasks: 0, total_touches: 0 })
const chartRef = ref<HTMLElement>()

onMounted(async () => {
  try {
    const { data } = await http.get('/api/dashboard/stats')
    stats.value = data
  } catch { /* API not ready */ }

  if (chartRef.value) {
    const chart = echarts.init(chartRef.value)
    chart.setOption({
      xAxis: { type: 'category', data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] },
      yAxis: { type: 'value' },
      series: [{ data: [0, 0, 0, 0, 0, 0, 0], type: 'line', smooth: true }],
    })
  }
})
</script>

<style scoped>
.stat-row { margin-bottom: 8px; }
</style>
