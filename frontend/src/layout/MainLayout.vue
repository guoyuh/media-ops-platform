<template>
  <el-container class="app-layout">
    <el-aside :width="sidebarCollapsed ? '64px' : '200px'">
      <div class="logo">{{ sidebarCollapsed ? 'M' : 'MediaOps' }}</div>
      <el-menu
        :default-active="route.path"
        :collapse="sidebarCollapsed"
        router
        background-color="#001529"
        text-color="#ffffffb3"
        active-text-color="#409eff"
      >
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <template #title>数据看板</template>
        </el-menu-item>
        <el-menu-item index="/collect">
          <el-icon><Search /></el-icon>
          <template #title>采集任务</template>
        </el-menu-item>
        <el-menu-item index="/media">
          <el-icon><Picture /></el-icon>
          <template #title>媒体资源</template>
        </el-menu-item>
        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <template #title>用户库</template>
        </el-menu-item>
        <el-menu-item index="/message">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>触达任务</template>
        </el-menu-item>
        <el-menu-item index="/accounts">
          <el-icon><Setting /></el-icon>
          <template #title>账号管理</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header>
        <el-button text @click="toggleSidebar">
          <el-icon :size="20"><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
        </el-button>
        <span class="header-title">自媒体运营平台</span>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { storeToRefs } from 'pinia'
import {
  DataBoard, Search, User, ChatDotRound, Setting, Fold, Expand, Picture,
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()
const { sidebarCollapsed } = storeToRefs(appStore)
const { toggleSidebar } = appStore
</script>

<style scoped>
.app-layout { height: 100vh; }
.el-aside {
  background: #001529;
  transition: width 0.3s;
  overflow: hidden;
}
.logo {
  height: 48px;
  line-height: 48px;
  text-align: center;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid #ffffff1a;
}
.el-header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
}
.header-title { margin-left: 12px; font-size: 16px; }
</style>
