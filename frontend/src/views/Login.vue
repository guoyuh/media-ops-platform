<template>
  <div class="login-container">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <h2 style="text-align: center; margin: 0">MediaOps Platform</h2>
      </template>

      <!-- 登录表单 -->
      <template v-if="!showRegister">
        <el-form :model="loginForm" @submit.prevent="handleLogin" label-position="top">
          <el-form-item label="用户名 / 邮箱">
            <el-input v-model="loginForm.account" placeholder="请输入用户名或邮箱" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" style="width: 100%" :loading="loading" @click="handleLogin">
              登录
            </el-button>
          </el-form-item>
        </el-form>
        <div class="switch-link">
          没有账号？<el-link type="primary" @click="showRegister = true">点击注册</el-link>
        </div>
      </template>

      <!-- 注册表单 -->
      <template v-else>
        <el-form :model="registerForm" @submit.prevent="handleRegister" label-position="top">
          <el-form-item label="用户名">
            <el-input v-model="registerForm.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="registerForm.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="registerForm.password" type="password" placeholder="至少6位" show-password />
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input v-model="registerForm.confirm_password" type="password" placeholder="再次输入密码" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" style="width: 100%" :loading="loading" @click="handleRegister">
              注册
            </el-button>
          </el-form-item>
        </el-form>
        <div class="switch-link">
          已有账号？<el-link type="primary" @click="showRegister = false">返回登录</el-link>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const showRegister = ref(false)
const loading = ref(false)

const loginForm = ref({ account: '', password: '' })
const registerForm = ref({ username: '', email: '', password: '', confirm_password: '' })

async function handleLogin() {
  if (!loginForm.value.account || !loginForm.value.password) {
    ElMessage.warning('请填写完整')
    return
  }
  loading.value = true
  try {
    const { data } = await http.post('/api/auth/login', loginForm.value)
    authStore.setAuth(data.token, data.user)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const f = registerForm.value
  if (!f.username || !f.email || !f.password || !f.confirm_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (f.password.length < 6) {
    ElMessage.warning('密码至少6位')
    return
  }
  if (f.password !== f.confirm_password) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await http.post('/api/auth/register', f)
    ElMessage.success('注册成功，请登录')
    showRegister.value = false
    loginForm.value.account = f.username
    loginForm.value.password = ''
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.login-card {
  width: 420px;
}
.switch-link {
  text-align: center;
  margin-top: 8px;
  color: #606266;
  font-size: 14px;
}
</style>
