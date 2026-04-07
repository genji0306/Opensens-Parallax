/**
 * Component Render Tests
 *
 * Tests that components mount without errors and render key elements.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('axios', () => {
  const instance = {
    get: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    post: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    defaults: { baseURL: '' },
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    create: vi.fn(),
  }
  instance.create.mockReturnValue(instance)
  return { default: instance }
})

vi.mock('@/stores/debug', () => ({
  useDebugStore: () => ({
    logRequest: vi.fn(() => 1),
    resolveRequest: vi.fn(),
    rejectRequest: vi.fn(),
    visible: false,
    requests: [],
    pendingCount: 0,
    errorCount: 0,
    okCount: 0,
    avgDuration: 0,
    toggle: vi.fn(),
    clear: vi.fn(),
  }),
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/project/:runId', component: { template: '<div>project</div>' } },
      { path: '/paper-lab', component: { template: '<div>paperlab</div>' } },
      { path: '/history', component: { template: '<div>history</div>' } },
    ],
  })
}

describe('Shared Components', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  describe('StatusBadge', () => {
    it('renders dot for status', async () => {
      const { default: StatusBadge } = await import('@/components/shared/StatusBadge.vue')

      const wrapper = mount(StatusBadge, {
        props: { status: 'done' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.status-badge__dot').exists()).toBe(true)
    })

    it('renders label when provided', async () => {
      const { default: StatusBadge } = await import('@/components/shared/StatusBadge.vue')

      const wrapper = mount(StatusBadge, {
        props: { status: 'failed', label: 'Failed' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Failed')
    })

    it('does not render label when omitted', async () => {
      const { default: StatusBadge } = await import('@/components/shared/StatusBadge.vue')

      const wrapper = mount(StatusBadge, {
        props: { status: 'pending' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.find('.status-badge__label').exists()).toBe(false)
    })
  })

  describe('MetricCard', () => {
    it('renders label and value', async () => {
      const { default: MetricCard } = await import('@/components/shared/MetricCard.vue')

      const wrapper = mount(MetricCard, {
        props: { label: 'Total Runs', value: '42' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Total Runs')
      expect(wrapper.text()).toContain('42')
    })
  })

  describe('ProgressBar', () => {
    it('renders', async () => {
      const { default: ProgressBar } = await import('@/components/shared/ProgressBar.vue')

      const wrapper = mount(ProgressBar, {
        props: { progress: 75 },
        global: { plugins: [pinia] },
      })

      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('GlassPanel', () => {
    it('renders slot content', async () => {
      const { default: GlassPanel } = await import('@/components/shared/GlassPanel.vue')

      const wrapper = mount(GlassPanel, {
        slots: { default: '<p>Test Content</p>' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Test Content')
    })
  })

  describe('ActionButton', () => {
    it('renders slot text and emits click', async () => {
      const { default: ActionButton } = await import('@/components/shared/ActionButton.vue')

      const wrapper = mount(ActionButton, {
        slots: { default: 'Start Pipeline' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Start Pipeline')
      await wrapper.find('button').trigger('click')
      expect(wrapper.emitted('click')).toBeTruthy()
    })

    it('renders disabled state', async () => {
      const { default: ActionButton } = await import('@/components/shared/ActionButton.vue')

      const wrapper = mount(ActionButton, {
        props: { disabled: true },
        slots: { default: 'Disabled' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    })

    it('shows spinner when loading', async () => {
      const { default: ActionButton } = await import('@/components/shared/ActionButton.vue')

      const wrapper = mount(ActionButton, {
        props: { loading: true },
        slots: { default: 'Loading...' },
        global: { plugins: [pinia] },
      })

      expect(wrapper.find('.action-btn__spinner').exists()).toBe(true)
      expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    })
  })
})

describe('Pipeline Components', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  describe('StageCard', () => {
    it('renders stage info with individual props', async () => {
      const { default: StageCard } = await import('@/components/pipeline/StageCard.vue')

      const wrapper = mount(StageCard, {
        props: {
          stageId: 'debate',
          title: 'Debate',
          icon: 'forum',
          status: 'done',
          metrics: [{ label: 'Agents', value: '6' }],
        },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Debate')
    })

    it('renders pending state', async () => {
      const { default: StageCard } = await import('@/components/pipeline/StageCard.vue')

      const wrapper = mount(StageCard, {
        props: {
          stageId: 'experiment',
          title: 'Experiment',
          icon: 'science',
          status: 'pending',
        },
        global: { plugins: [pinia] },
      })

      expect(wrapper.text()).toContain('Experiment')
    })

    it('renders failed state', async () => {
      const { default: StageCard } = await import('@/components/pipeline/StageCard.vue')

      const wrapper = mount(StageCard, {
        props: {
          stageId: 'crawl',
          title: 'Crawl',
          icon: 'search',
          status: 'failed',
        },
        global: { plugins: [pinia] },
      })

      expect(wrapper.html()).toBeTruthy()
    })
  })

  describe('ProjectCard', () => {
    it('renders project summary', async () => {
      const { default: ProjectCard } = await import('@/components/pipeline/ProjectCard.vue')
      const router = createTestRouter()
      await router.push('/')
      await router.isReady()

      const wrapper = mount(ProjectCard, {
        props: {
          project: {
            id: 'test_run_abc',
            run_id: 'test_run_abc',
            title: 'Electrochemical Testing',
            topic: 'Electrochemical Testing',
            type: 'debate' as const,
            status: 'completed',
            created_at: '2026-03-21T23:09:00',
            updated_at: '2026-03-21T23:09:00',
          },
        },
        global: { plugins: [pinia, router] },
      })

      expect(wrapper.text()).toContain('Electrochemical Testing')
    })

    it('maps review_complete to a done badge', async () => {
      const { default: ProjectCard } = await import('@/components/pipeline/ProjectCard.vue')
      const router = createTestRouter()
      await router.push('/')
      await router.isReady()

      const wrapper = mount(ProjectCard, {
        props: {
          project: {
            id: 'upload_001',
            run_id: 'upload_001',
            title: 'Paper Rehab',
            topic: 'Paper Rehab',
            type: 'paper' as const,
            status: 'review_complete',
            created_at: '2026-03-21T23:09:00',
            updated_at: '2026-03-21T23:09:00',
          },
        },
        global: { plugins: [pinia, router] },
      })

      expect(wrapper.find('.status-badge--done').exists()).toBe(true)
    })
  })
})

// ── P-2/P-3/P-6 Component Mount Tests ────────────────────────────────

describe('Knowledge Components', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    router = createTestRouter()
  })

  describe('NoveltyMap', () => {
    it('renders with button when no data loaded', async () => {
      const NoveltyMap = (await import('@/components/knowledge/NoveltyMap.vue')).default
      const wrapper = mount(NoveltyMap, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.novelty-map').exists()).toBe(true)
      expect(wrapper.find('.novelty-map__btn').exists()).toBe(true)
      expect(wrapper.text()).toContain('Map Novelty')
    })
  })

  describe('QuestionTree', () => {
    it('renders with decompose button', async () => {
      const QuestionTree = (await import('@/components/knowledge/QuestionTree.vue')).default
      const wrapper = mount(QuestionTree, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.question-tree').exists()).toBe(true)
      expect(wrapper.find('.question-tree__btn').exists()).toBe(true)
      expect(wrapper.text()).toContain('Decompose')
    })
  })

  describe('HypothesisCard', () => {
    it('renders with build button when no hypothesis', async () => {
      const HypothesisCard = (await import('@/components/knowledge/HypothesisCard.vue')).default
      const wrapper = mount(HypothesisCard, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.hypothesis-card').exists()).toBe(true)
      expect(wrapper.find('.hypothesis-card__btn').exists()).toBe(true)
      expect(wrapper.text()).toContain('Build Hypothesis')
    })
  })

  describe('GrantPreview', () => {
    it('renders with data', async () => {
      const GrantPreview = (await import('@/components/knowledge/GrantPreview.vue')).default
      const wrapper = mount(GrantPreview, {
        props: {
          data: {
            title: 'Test Grant',
            executive_summary: 'Summary text',
            innovation_trl: { current_trl: 3, target_trl: 6, trl_justification: 'Lab validated' },
            expected_outcomes: ['Outcome A', 'Outcome B'],
            timeline_months: 24,
          },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.grant-preview').exists()).toBe(true)
      expect(wrapper.text()).toContain('Test Grant')
      expect(wrapper.text()).toContain('Summary text')
      expect(wrapper.text()).toContain('24 months')
    })

    it('renders nothing when data is null', async () => {
      const GrantPreview = (await import('@/components/knowledge/GrantPreview.vue')).default
      const wrapper = mount(GrantPreview, {
        props: { data: null },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.grant-preview').exists()).toBe(false)
    })
  })
})

describe('Review Components', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    router = createTestRouter()
  })

  describe('ReviewConflictPanel', () => {
    it('renders with analyze button', async () => {
      const ReviewConflictPanel = (await import('@/components/review/ReviewConflictPanel.vue')).default
      const wrapper = mount(ReviewConflictPanel, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.conflict-panel').exists()).toBe(true)
      expect(wrapper.find('.conflict-panel__btn').exists()).toBe(true)
      expect(wrapper.text()).toContain('Analyze')
    })
  })

  describe('RevisionPlanView', () => {
    it('renders with create plan and generate rebuttal buttons', async () => {
      const RevisionPlanView = (await import('@/components/review/RevisionPlanView.vue')).default
      const wrapper = mount(RevisionPlanView, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.revision-plan').exists()).toBe(true)
      expect(wrapper.text()).toContain('Create Plan')
      expect(wrapper.text()).toContain('Generate Rebuttal')
    })
  })

  describe('ConsistencyReport', () => {
    it('renders empty state with no contradictions', async () => {
      const ConsistencyReport = (await import('@/components/review/ConsistencyReport.vue')).default
      const wrapper = mount(ConsistencyReport, {
        props: {
          data: { contradictions: [], consistency_score: 9, summary: 'All consistent' },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.consistency-report').exists()).toBe(true)
      expect(wrapper.text()).toContain('All consistent')
      expect(wrapper.text()).toContain('No contradictions')
    })

    it('renders contradictions when present', async () => {
      const ConsistencyReport = (await import('@/components/review/ConsistencyReport.vue')).default
      const wrapper = mount(ConsistencyReport, {
        props: {
          data: {
            contradictions: [
              { type: 'text_vs_figure', severity: 'major', description: 'Fig 1 contradicts text', recommendation: 'Fix caption' },
            ],
            consistency_score: 5,
            summary: 'Issues found',
          },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.contradiction-card').exists()).toBe(true)
      expect(wrapper.text()).toContain('Fig 1 contradicts text')
    })
  })
})

describe('Handoff Components', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    router = createTestRouter()
  })

  describe('ReadinessPanel', () => {
    it('renders with heading', async () => {
      const ReadinessPanel = (await import('@/components/handoff/ReadinessPanel.vue')).default
      const wrapper = mount(ReadinessPanel, {
        props: { runId: 'test_run' },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.readiness-panel').exists()).toBe(true)
      expect(wrapper.text()).toContain('Platform Readiness')
    })
  })
})

describe('Pipeline Components (P-1)', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    router = createTestRouter()
  })

  describe('StageSettingsForm', () => {
    it('renders search stage settings with source chips and max papers slider', async () => {
      const StageSettingsForm = (await import('@/components/pipeline/StageSettingsForm.vue')).default
      const wrapper = mount(StageSettingsForm, {
        props: {
          stageId: 'crawl',
          modelValue: { sources: ['arxiv'], max_papers: 100 },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.stage-settings').exists()).toBe(true)
      expect(wrapper.text()).toContain('Literature Search Settings')
      // Should have source chips
      expect(wrapper.findAll('.stage-settings__chip').length).toBeGreaterThan(0)
      // Should have slider
      expect(wrapper.find('input[type="range"]').exists()).toBe(true)
    })

    it('renders debate settings with rounds and agents sliders', async () => {
      const StageSettingsForm = (await import('@/components/pipeline/StageSettingsForm.vue')).default
      const wrapper = mount(StageSettingsForm, {
        props: {
          stageId: 'debate',
          modelValue: { max_rounds: 5, agents: 6, format: 'adversarial' },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.text()).toContain('Agent Debate Settings')
      expect(wrapper.findAll('input[type="range"]').length).toBeGreaterThanOrEqual(2)
      expect(wrapper.find('select').exists()).toBe(true)
    })

    it('renders nothing for pass stage (no fields)', async () => {
      const StageSettingsForm = (await import('@/components/pipeline/StageSettingsForm.vue')).default
      const wrapper = mount(StageSettingsForm, {
        props: {
          stageId: 'pass',
          modelValue: {},
        },
        global: { plugins: [pinia, router] },
      })
      // Pass stage has no fields, so the component should not render
      expect(wrapper.find('.stage-settings').exists()).toBe(false)
    })

    it('emits update on field change', async () => {
      const StageSettingsForm = (await import('@/components/pipeline/StageSettingsForm.vue')).default
      const wrapper = mount(StageSettingsForm, {
        props: {
          stageId: 'rehab',
          modelValue: { min_score: 6.0, max_revisions: 3 },
        },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.text()).toContain('Revision Settings')
      // Change a slider value
      const slider = wrapper.find('input[type="range"]')
      await slider.setValue(8)
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    })
  })

  describe('FigureCritiquePanel', () => {
    it('renders empty state', async () => {
      const FigureCritiquePanel = (await import('@/components/stages/FigureCritiquePanel.vue')).default
      const wrapper = mount(FigureCritiquePanel, {
        props: { result: {} },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.figure-critique').exists()).toBe(true)
      expect(wrapper.text()).toContain('No figure critique data')
    })
  })

  describe('TableAnalysisPanel', () => {
    it('renders empty state', async () => {
      const TableAnalysisPanel = (await import('@/components/stages/TableAnalysisPanel.vue')).default
      const wrapper = mount(TableAnalysisPanel, {
        props: { data: null },
        global: { plugins: [pinia, router] },
      })
      expect(wrapper.find('.table-analysis').exists()).toBe(true)
      expect(wrapper.text()).toContain('No table analysis data')
    })
  })
})
