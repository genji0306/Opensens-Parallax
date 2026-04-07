import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'command-center',
    component: () => import('../views/CommandCenter.vue'),
  },
  {
    path: '/project/:runId',
    name: 'project',
    component: () => import('../views/ProjectDetail.vue'),
    props: true,
  },
  {
    path: '/paper-lab',
    name: 'paper-lab',
    component: () => import('../views/PaperLab.vue'),
  },
  {
    path: '/grants',
    name: 'grant-hunt',
    component: () => import('../views/GrantHunt.vue'),
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('../views/History.vue'),
  },
  {
    path: '/v3/debate/:runId',
    name: 'debate-analysis',
    component: () => import('../views/DebateAnalysis.vue'),
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
