import { createRouter, createWebHistory } from 'vue-router'
import AuthView from './views/AuthView.vue'
import ChatView from './views/ChatView.vue'

const routes = [
  { path: '/auth', component: AuthView, meta: { guest: true } },
  { path: '/', component: ChatView, meta: { requiresAuth: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/auth')
  } else if (to.meta.guest && token) {
    next('/')
  } else {
    next()
  }
})

export default router