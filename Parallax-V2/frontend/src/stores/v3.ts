/**
 * V3 Gateway store — manages V3 projects, costs, events, and approvals.
 *
 * This store complements the existing pipeline/projects stores by adding
 * V3-specific state: real cost tracking, DRVP events, budget status,
 * and governance approvals.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  v3Projects, v3Costs, v3Approvals, v3Templates,
  createEventStream,
  type V3Project, type V3CostSummary, type V3BudgetStatus,
  type V3DRVPEvent, type V3Approval, type V3Template,
} from '@/api/v3'

export const useV3Store = defineStore('v3', () => {
  // ── State ──────────────────────────────────────────────────

  /** Active V3 project */
  const activeProject = ref<V3Project | null>(null)

  /** Cost summary for the active project */
  const projectCost = ref<V3CostSummary | null>(null)

  /** Budget status for the active project */
  const budget = ref<V3BudgetStatus | null>(null)

  /** DRVP event stream (most recent first, capped at 200) */
  const events = ref<V3DRVPEvent[]>([])
  const maxEvents = 200

  /** Pending approvals */
  const pendingApprovals = ref<V3Approval[]>([])

  /** Available protocol templates */
  const templates = ref<V3Template[]>([])

  /** SSE connection state */
  const eventStreamConnected = ref(false)
  let _eventSource: EventSource | null = null

  // ── Computed ───────────────────────────────────────────────

  const totalCostUsd = computed(() => projectCost.value?.total_cost_usd ?? 0)

  const budgetRemaining = computed(() => budget.value?.remaining_usd ?? 0)

  const budgetPct = computed(() => {
    if (!budget.value || budget.value.cap_usd <= 0) return 0
    return Math.round((budget.value.spent_usd / budget.value.cap_usd) * 100)
  })

  const recentEvents = computed(() => events.value.slice(0, 50))

  const pendingApprovalCount = computed(() => pendingApprovals.value.length)

  // ── Actions ────────────────────────────────────────────────

  async function loadTemplates() {
    try {
      templates.value = await v3Templates.list()
    } catch {
      templates.value = []
    }
  }

  async function loadProject(projectId: string) {
    activeProject.value = await v3Projects.get(projectId)
    await Promise.all([
      refreshCost(projectId),
      refreshBudget(projectId),
      refreshApprovals(projectId),
    ])
  }

  async function createProject(data: {
    name: string
    description?: string
    domain?: string
    template_id?: string
    budget_cap_usd?: number
  }) {
    const project = await v3Projects.create(data)
    activeProject.value = project
    return project
  }

  async function refreshCost(projectId?: string) {
    const id = projectId || activeProject.value?.project_id
    if (!id) return
    try {
      projectCost.value = await v3Costs.project(id)
    } catch {
      projectCost.value = null
    }
  }

  async function refreshBudget(projectId?: string) {
    const id = projectId || activeProject.value?.project_id
    if (!id) return
    try {
      budget.value = await v3Costs.budget(id)
    } catch {
      budget.value = null
    }
  }

  async function refreshApprovals(projectId?: string) {
    const id = projectId || activeProject.value?.project_id
    try {
      pendingApprovals.value = await v3Approvals.list('pending', id || undefined)
    } catch {
      pendingApprovals.value = []
    }
  }

  async function approveRequest(approvalId: string) {
    await v3Approvals.decide(approvalId, 'approved')
    await refreshApprovals()
  }

  async function denyRequest(approvalId: string, reason = '') {
    await v3Approvals.decide(approvalId, 'denied', 'local', reason)
    await refreshApprovals()
  }

  // ── DRVP Event Stream ──────────────────────────────────────

  function connectEventStream() {
    if (_eventSource) return // Already connected

    _eventSource = createEventStream(
      (event) => {
        // Prepend event (newest first)
        events.value = [event, ...events.value].slice(0, maxEvents)

        // Auto-refresh cost on cost-related events
        if (event.event_type === 'phase.completed' || event.event_type === 'budget.warning') {
          refreshCost()
          refreshBudget()
        }

        // Auto-refresh approvals on approval events
        if (event.event_type === 'approval.required') {
          refreshApprovals()
        }
      },
      () => {
        eventStreamConnected.value = false
        // Auto-reconnect after 3s
        setTimeout(() => {
          _eventSource = null
          connectEventStream()
        }, 3000)
      },
    )

    eventStreamConnected.value = true
  }

  function disconnectEventStream() {
    _eventSource?.close()
    _eventSource = null
    eventStreamConnected.value = false
  }

  function clearEvents() {
    events.value = []
  }

  // ── Cleanup ────────────────────────────────────────────────

  function $reset() {
    disconnectEventStream()
    activeProject.value = null
    projectCost.value = null
    budget.value = null
    events.value = []
    pendingApprovals.value = []
  }

  return {
    // State
    activeProject,
    projectCost,
    budget,
    events,
    pendingApprovals,
    templates,
    eventStreamConnected,

    // Computed
    totalCostUsd,
    budgetRemaining,
    budgetPct,
    recentEvents,
    pendingApprovalCount,

    // Actions
    loadTemplates,
    loadProject,
    createProject,
    refreshCost,
    refreshBudget,
    refreshApprovals,
    approveRequest,
    denyRequest,
    connectEventStream,
    disconnectEventStream,
    clearEvents,
    $reset,
  }
})
