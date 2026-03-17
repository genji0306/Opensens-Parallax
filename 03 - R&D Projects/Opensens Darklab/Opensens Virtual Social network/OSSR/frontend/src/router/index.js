import { createRouter, createWebHistory } from 'vue-router'
import ResearchDashboard from '../views/ResearchDashboard.vue'

const routes = [
  {
    path: '/',
    name: 'research',
    component: ResearchDashboard,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
