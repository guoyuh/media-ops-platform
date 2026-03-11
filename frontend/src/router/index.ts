import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'collect', name: 'CollectTask', component: () => import('../views/CollectTask.vue') },
      // { path: 'media', name: 'MediaGallery', component: () => import('../views/MediaGallery.vue') },
      { path: 'users', name: 'UserPool', component: () => import('../views/UserPool.vue') },
      { path: 'message', name: 'MessageTask', component: () => import('../views/MessageTask.vue') },
      // { path: 'creative', name: 'CreativeWrite', component: () => import('../views/CreativeWrite.vue') },
      { path: 'accounts', name: 'AccountManage', component: () => import('../views/AccountManage.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) return '/login'
  if (to.path === '/login' && token) return '/'
})

export default router
