<template>
  <el-container class="app-layout">
    <el-aside
      :width="sidebarCollapsed ? '64px' : '200px'"
      @mouseenter="sidebarCollapsed = false"
      @mouseleave="sidebarCollapsed = true"
    >
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
          <template #title>媒体库</template>
        </el-menu-item>
        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <template #title>用户库</template>
        </el-menu-item>
        <el-menu-item index="/message">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>触达任务</template>
        </el-menu-item>
        <el-menu-item index="/creative">
          <el-icon><Edit /></el-icon>
          <template #title>创作中心</template>
        </el-menu-item>
        <el-menu-item index="/accounts">
          <el-icon><Setting /></el-icon>
          <template #title>Cookie管理</template>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-bottom">
        <div class="user-info" v-if="!sidebarCollapsed">
          <div class="username">{{ authStore.user?.username || '未登录' }}</div>
        </div>
        <div class="user-info-collapsed" v-else>
          <el-tooltip :content="authStore.user?.username || '未登录'" placement="right">
            <div class="username-icon">{{ (authStore.user?.username || 'U')[0].toUpperCase() }}</div>
          </el-tooltip>
        </div>
        <el-menu
          :collapse="sidebarCollapsed"
          background-color="#001529"
          text-color="#ffffffb3"
          active-text-color="#409eff"
          class="logout-menu"
        >
          <el-menu-item index="" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            <template #title>退出登录</template>
          </el-menu-item>
        </el-menu>
      </div>
    </el-aside>
    <el-container>
      <el-header>
        <span class="header-title">自媒体运营平台</span>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ref } from 'vue'
import {
  DataBoard, Search, Picture, User, ChatDotRound, Edit, Setting, SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const sidebarCollapsed = ref(true)

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout { height: 100vh; }
.el-aside {
  background: #001529;
  transition: width 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
.el-aside > .el-menu {
  flex: 1;
  border-right: none;
}
.sidebar-bottom {
  border-top: 1px solid #ffffff1a;
}
.user-info {
  padding: 12px 16px;
  color: #ffffffb3;
  font-size: 14px;
  border-bottom: 1px solid #ffffff1a;
}
.username {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-info-collapsed {
  display: flex;
  justify-content: center;
  padding: 12px 0;
  border-bottom: 1px solid #ffffff1a;
}
.username-icon {
  width: 32px;
  height: 32px;
  line-height: 32px;
  text-align: center;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 14px;
  font-weight: bold;
}
.logout-menu {
  border-right: none;
}
.el-header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
}
.header-title { font-size: 16px; }
</style>
