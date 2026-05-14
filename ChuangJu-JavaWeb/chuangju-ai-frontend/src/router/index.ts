// 文件: src/router/index.ts

import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      // 重定向到我们的第一个功能页面：智能打标
      redirect: '/tagging'
    },
    {
      path: '/tagging',
      name: 'tagging',
      // 路由懒加载：只有当访问这个页面时，才会加载对应的组件代码
      component: () => import('../views/TaggingView.vue')
    },
    {
      path: '/gallery',
      name: 'gallery',
      component: () => import('../views/GalleryView.vue')
    },
    {
      path: '/nlp-search',
      name: 'nlp-search',
      component: () => import('../views/NlpSearchView.vue')
    },
    {
      path: '/floorplan-design',
      name: 'floorplan-design',
      component: () => import('../views/FloorplanDesignView.vue')
    }
  ]
})

export default router
