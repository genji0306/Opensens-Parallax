import { createRouter, createWebHistory } from 'vue-router'
import ResearchDashboard from '../views/ResearchDashboard.vue'

const routes = [
  {
    path: '/',
    name: 'research',
    component: ResearchDashboard,
  },
  {
    path: '/console/:simId',
    name: 'console',
    component: () => import('../views/ResearchConsole.vue'),
    props: true,
  },
  {
    path: '/ais',
    name: 'ais',
    component: () => import('../views/AisPipelineView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
