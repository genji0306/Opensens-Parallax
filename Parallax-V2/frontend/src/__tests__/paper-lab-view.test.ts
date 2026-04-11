import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import * as paperLabApi from '@/api/paperLab'

vi.mock('@/api/paperLab', () => ({
  uploadPaper: vi.fn(),
  getUploadStatus: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        upload_id: 'paper_1',
        title: 'Structured Battery Study',
        language: 'en',
        field: 'energy_systems',
        detected_field: 'energy_systems',
        parser_engine: 'opendataloader_pdf',
        parser_mode: 'layout_aware',
        parse_quality: {
          overall: 0.91,
          title_confidence: 0.98,
          section_coverage: 0.94,
          reading_order: 0.89,
          table_retention: 0.87,
          figure_retention: 0.92,
          formula_retention: 0.75,
        },
        parse_quality_breakdown: {
          overall: 0.91,
          title_confidence: 0.98,
          section_coverage: 0.94,
          reading_order: 0.89,
          table_retention: 0.87,
          figure_retention: 0.92,
          formula_retention: 0.75,
        },
        parse_warnings: ['Potential two-column ordering issue on page 4'],
        ocr_used: false,
        document_counts: {
          sections: 8,
          tables: 2,
          figures: 3,
          formulas: 1,
          references: 24,
        },
        sections: ['Abstract', 'Methods', 'Results', 'Discussion'],
        tables: [{ table_id: 'T1', markdown: '| A | B |', page: 3 }, { table_id: 'T2', markdown: '| C | D |', page: 5 }],
        figures: [{ figure_id: 'F1', caption: 'Lifecycle retention under accelerated testing.', page: 4 }, { figure_id: 'F2' }, { figure_id: 'F3' }],
        formulas: [{ formula_id: 'Eq1', latex: 'E = mc^2', page: 6 }],
        status: 'review_complete',
        review_scores: [5.4, 6.8],
        round_count: 1,
        created_at: '2026-04-11T12:00:00',
      },
    },
  }),
  startReview: vi.fn().mockResolvedValue({ data: { success: true, data: { session_id: 'sess_1' } } }),
  getRounds: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        rounds: [
          {
            round_num: 1,
            review: {
              avg_overall_score: 6.8,
              final_decision: 'major_revision',
              all_weaknesses: [{ text: 'Results need a stronger figure-driven explanation.' }],
            },
            revision: {
              triage: [{ weakness: 'Results need a stronger figure-driven explanation.', action: 'accept' }],
            },
          },
        ],
        score_progression: [5.4, 6.8],
        reviewers: [],
        source_audit: { verified: ['Ref A'], unverified: [], method: 'heuristic' },
      },
    },
  }),
  getDraft: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        title: 'Structured Battery Study',
        draft: 'This is the refined draft text for the manuscript.',
        word_count: 1234,
        status: 'review_complete',
      },
    },
  }),
  listUploads: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: [
        {
          upload_id: 'paper_1',
          title: 'Structured Battery Study',
          language: 'en',
          field: 'energy_systems',
          parser_engine: 'opendataloader_pdf',
          parser_mode: 'layout_aware',
          parse_quality: { overall: 0.91 },
          ocr_used: false,
          document_counts: {
            sections: 8,
            tables: 2,
            figures: 3,
            formulas: 1,
            references: 24,
          },
          status: 'review_complete',
          review_scores: [5.4, 6.8],
          round_count: 1,
          created_at: '2026-04-11T12:00:00',
        },
      ],
    },
  }),
  runSpecialistReview: vi.fn(),
  getSpecialistReview: vi.fn().mockResolvedValue({
    data: { success: true, data: { reviews: [{ findings: [{ description: 'Need stronger lifecycle figure.' }] }] } },
  }),
  exportDocx: vi.fn(),
  getResponseToReviewers: vi.fn(),
  getRewriteInstructions: vi.fn(),
  subscribeToProgress: vi.fn((_uploadId, _sessionId, onEvent) => {
    onEvent({ type: 'stream_error', data: { message: 'SSE connection lost' } })
    return vi.fn()
  }),
  listVisualizationArtifacts: vi.fn().mockResolvedValue({ data: { success: true, data: [] } }),
  getVisualizationPlan: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        reconstruct: [],
        improve: [],
        create_missing: [],
        graphical_abstract: [],
        communication_outputs: [],
      },
    },
  }),
  createVisualizationArtifact: vi.fn(),
  renderVisualizationArtifact: vi.fn(),
  auditVisualizationArtifact: vi.fn(),
  exportVisualizationArtifact: vi.fn().mockResolvedValue({ data: { success: true, data: { ready: false } } }),
  generateGraphicalAbstract: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
  generateSlideStarter: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
  generatePosterStarter: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
  refinePaperSection: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        refinement_id: 'refine_1',
        action: 'improve_introduction',
        section: 'Introduction',
        original_text: 'Old text',
        revised_text: 'New text',
        applied: false,
        diff: { before_word_count: 2, after_word_count: 2, summary: 'Refined section.' },
        addressed_recommendations: ['Clarify motivation'],
      },
    },
  }),
  applyPaperRefinement: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        upload_id: 'paper_1',
        refinement_id: 'refine_1',
        section: 'Introduction',
        current_draft: 'New text',
        sections: [{ name: 'Introduction', content: 'New text' }],
      },
    },
  }),
  getDraftHistory: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        upload_id: 'paper_1',
        applied_refinements: [],
        section_refinement_history: [],
        grounded_literature_history: [],
      },
    },
  }),
  revertPaperRefinement: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        upload_id: 'paper_1',
        reverted_refinement_id: 'refine_1',
        current_draft: 'Old text',
        sections: [{ name: 'Introduction', content: 'Old text' }],
      },
    },
  }),
  groundedLiteratureReview: vi.fn().mockResolvedValue({
    data: {
      success: true,
      data: {
        focus: 'literature review',
        queries: ['query one'],
        suggestions: [
          {
            citation_id: 'c1',
            title: 'Verified paper',
            doi: '10.1000/test',
            year: '2025',
            source: 'local_db',
            verified: true,
            confidence: 0.9,
            query: 'query one',
            insertion_point: 'Introduction',
            provenance: {},
          },
        ],
        ready: true,
        unverified_count: 0,
        note: 'Only verified citations should be promoted to ready state.',
      },
    },
  }),
}))

vi.mock('@/api/ais', () => ({
  exportDraft: vi.fn(),
}))

vi.mock('@/stores/debug', () => ({
  useDebugStore: () => ({
    logRequest: vi.fn(() => 1),
    resolveRequest: vi.fn(),
    rejectRequest: vi.fn(),
  }),
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/paper-lab', name: 'paper-lab', component: { template: '<div />' } }],
  })
}

describe('PaperLab view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('syncs selected upload into the route and renders review overview', async () => {
    const router = createTestRouter()
    await router.push('/paper-lab')
    await router.isReady()
    const { default: PaperLab } = await import('@/views/PaperLab.vue')

    const wrapper = mount(PaperLab, {
      global: {
        plugins: [router],
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()

    await wrapper.find('.upload-item').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.upload_id).toBe('paper_1')
    expect(wrapper.text()).toContain('Review Overview')
    expect(wrapper.text()).toContain('Results need a stronger figure-driven explanation.')
    expect(wrapper.text()).toContain('Opendataloader Pdf')
    expect(wrapper.text()).toContain('Parse Quality:')
    expect(wrapper.text()).toContain('Figures')
    expect(wrapper.text()).toContain('Document Parse')
    expect(wrapper.text()).toContain('Potential two-column ordering issue on page 4')
    expect(wrapper.text()).toContain('Reading order')
    expect(wrapper.text()).toContain('| A | B |')
    expect(wrapper.text()).toContain('Lifecycle retention under accelerated testing.')
    expect(wrapper.text()).toContain('E = mc^2')
    expect(wrapper.text()).toContain('Page 3')
    expect(wrapper.text()).toContain('Page 4')
    expect(wrapper.text()).toContain('Page 6')
  })

  it('clears review loading and shows stream failure notice', async () => {
    vi.mocked(paperLabApi.listUploads).mockResolvedValueOnce({
      data: {
        success: true,
        data: [
          {
            upload_id: 'paper_2',
            title: 'Pre-Review Manuscript',
            language: 'en',
            field: 'energy_systems',
            status: 'parsed',
            review_scores: [],
            round_count: 0,
            created_at: '2026-04-11T12:00:00',
          },
        ],
      },
    } as never)
    vi.mocked(paperLabApi.getUploadStatus).mockResolvedValue({
      data: {
        success: true,
        data: {
          upload_id: 'paper_2',
          title: 'Pre-Review Manuscript',
          language: 'en',
          field: 'energy_systems',
          detected_field: 'energy_systems',
          parser_engine: 'legacy_text',
          parser_mode: 'direct',
          parse_quality: { overall: 0.83 },
          parse_quality_breakdown: { overall: 0.83, section_coverage: 0.8 },
          parse_warnings: [],
          ocr_used: false,
          document_counts: {
            sections: 3,
            tables: 0,
            figures: 0,
            formulas: 0,
            references: 0,
          },
          sections: ['Abstract', 'Methods', 'Results'],
          tables: [],
          figures: [],
          formulas: [],
          status: 'parsed',
          review_scores: [],
          round_count: 0,
          created_at: '2026-04-11T12:00:00',
        },
      },
    })

    const router = createTestRouter()
    await router.push('/paper-lab')
    await router.isReady()
    const { default: PaperLab } = await import('@/views/PaperLab.vue')

    const wrapper = mount(PaperLab, {
      global: {
        plugins: [router],
      },
    })

    await flushPromises()
    await wrapper.find('.upload-item').trigger('click')
    await flushPromises()
    const startButton = wrapper.findAll('button').find(node => node.text().includes('Start Adversarial Review'))
    expect(startButton).toBeTruthy()
    await startButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Live progress connection was lost')
    expect(wrapper.text()).not.toContain('Reviewers evaluating manuscript...')
  })

  it('allows pdf and doc uploads in the file picker', async () => {
    vi.mocked(paperLabApi.listUploads).mockResolvedValueOnce({
      data: {
        success: true,
        data: [],
      },
    } as never)

    const router = createTestRouter()
    await router.push('/paper-lab')
    await router.isReady()
    const { default: PaperLab } = await import('@/views/PaperLab.vue')

    const wrapper = mount(PaperLab, {
      global: {
        plugins: [router],
      },
    })

    await flushPromises()

    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)
    expect(fileInput.attributes('accept')).toBe('.pdf,.doc,.docx,.txt,.md,.markdown')
    expect(wrapper.text()).toContain('Drop a .pdf, .doc, .docx, .txt, .md, or .markdown file here')
  })
})
