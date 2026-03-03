import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'collect', name: 'CollectTask', component: () => import('../views/CollectTask.vue') },
      { path: 'media', name: 'MediaGallery', component: () => import('../views/MediaGallery.vue') },
      { path: 'users', name: 'UserPool', component: () => import('../views/UserPool.vue') },
      { path: 'message', name: 'MessageTask', component: () => import('../views/MessageTask.vue') },
      { path: 'accounts', name: 'AccountManage', component: () => import('../views/AccountManage.vue') },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
