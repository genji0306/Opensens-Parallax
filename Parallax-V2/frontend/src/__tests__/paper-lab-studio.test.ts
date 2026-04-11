import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VisualizationStudio from '@/components/paper/VisualizationStudio.vue'
import * as paperLabApi from '@/api/paperLab'

const fixtureState = vi.hoisted(() => {
  const artifactFixtures = [
    {
      artifact_id: 'viz_1',
      upload_id: 'paper_1',
      type: 'chart',
      intent: 'reconstruct',
      title: 'Figure 2',
      status: 'needs_input',
      version: 1,
      payload: {
        assumptions: ['Confirm data values'],
        source_refs: ['Figure 2'],
        source_sections: ['Results'],
        linked_review_findings: ['Clarify statistical significance'],
        rendering: {
          spec: {
            mark: 'bar',
            encoding: {
              x: { field: 'condition', type: 'nominal' },
              y: { field: 'performance', type: 'quantitative' },
            },
          },
        },
      },
      audit: { consistency_status: 'warn', issues: ['Resolve assumptions'], confidence: 0.74, ready: false },
      provenance: { generated_by: 'paper_orchestra_service', source: 'paper_lab', model: 'gpt-5.4' },
      created_at: '2026-04-11T12:00:00',
      updated_at: '2026-04-11T12:00:00',
    },
    {
      artifact_id: 'viz_2',
      upload_id: 'paper_1',
      type: 'slide',
      intent: 'summarize',
      title: 'Slide Starter',
      status: 'ready',
      version: 1,
      payload: {
        slides: [
          { title: 'Problem', summary: 'Summarize the problem.' },
          { title: 'Results', summary: 'Summarize the results.' },
        ],
      },
      audit: { consistency_status: 'pass', issues: [] },
      provenance: {},
      created_at: '2026-04-11T12:00:00',
      updated_at: '2026-04-11T12:00:00',
    },
  ]

  const cloneArtifacts = () => artifactFixtures.map(artifact => ({
    ...artifact,
    payload: JSON.parse(JSON.stringify(artifact.payload)),
    audit: JSON.parse(JSON.stringify(artifact.audit)),
    provenance: { ...artifact.provenance },
  }))

  return {
    artifactFixtures,
    cloneArtifacts,
    artifactsState: cloneArtifacts(),
  }
})

vi.mock('@/api/paperLab', async () => {
  const actual = await vi.importActual<typeof import('@/api/paperLab')>('@/api/paperLab')
  return {
    ...actual,
    listVisualizationArtifacts: vi.fn().mockResolvedValue({
      data: { success: true, data: fixtureState.artifactsState },
    }),
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
    exportVisualizationArtifact: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          ready: false,
          blocked_by: ['Confirm data values'],
        },
      },
    }),
    updateVisualizationArtifact: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          artifact_id: 'viz_1',
          upload_id: 'paper_1',
          type: 'chart',
          intent: 'reconstruct',
          title: 'Figure 2 Updated',
          status: 'draft',
          version: 2,
          payload: {
            assumptions: [],
            data_contract: { mode: 'user_supplied' },
          },
          audit: { consistency_status: 'warn', issues: ['Resolve assumptions'] },
          provenance: {},
          created_at: '2026-04-11T12:00:00',
          updated_at: '2026-04-11T12:05:00',
        },
      },
    }),
    refinePaperSection: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          refinement_id: 'refine_1',
          action: 'improve_introduction',
          section: 'Introduction',
          original_text: 'Old intro',
          revised_text: 'New intro',
          applied: false,
          diff: { before_word_count: 2, after_word_count: 2, summary: 'Refined intro.' },
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
          current_draft: 'New intro\n\nMethods...',
          sections: [{ name: 'Introduction', content: 'New intro' }],
        },
      },
    }),
    getDraftHistory: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          upload_id: 'paper_1',
          applied_refinements: [
            {
              refinement_id: 'refine_0',
              action: 'rewrite_methods_for_clarity',
              section: 'Methods',
              applied_at: '2026-04-11T11:00:00',
            },
          ],
          section_refinement_history: [],
          grounded_literature_history: [
            {
              focus: 'battery benchmark',
              ready: true,
              suggestion_count: 3,
              verified_count: 3,
              created_at: '2026-04-11T11:05:00',
            },
          ],
          last_applied_refinement_id: 'refine_0',
        },
      },
    }),
    revertPaperRefinement: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          upload_id: 'paper_1',
          reverted_refinement_id: 'refine_0',
          current_draft: 'Restored draft snapshot',
          sections: [{ name: 'Methods', content: 'Original methods text' }],
        },
      },
    }),
    groundedLiteratureReview: vi.fn().mockResolvedValue({
      data: {
        success: true,
        data: {
          focus: 'literature review',
          queries: ['query one'],
          suggestions: [],
          ready: true,
          unverified_count: 0,
          note: 'Only verified citations should be promoted to ready state.',
        },
      },
    }),
    renderVisualizationArtifact: vi.fn().mockResolvedValue({ data: { success: true, data: null } }),
    auditVisualizationArtifact: vi.fn().mockResolvedValue({ data: { success: true, data: null } }),
    createVisualizationArtifact: vi.fn(),
    generateGraphicalAbstract: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    generateSlideStarter: vi.fn().mockImplementation(async () => {
      fixtureState.artifactsState = [
        ...fixtureState.artifactsState,
        {
          artifact_id: 'viz_3',
          upload_id: 'paper_1',
          type: 'slide',
          intent: 'summarize',
          title: 'Scientific Slide Starter',
          status: 'ready',
          version: 1,
          payload: {
            slides: [
              { title: 'Problem', summary: 'Frame the research problem.' },
              { title: 'Conclusion', summary: 'State the key conclusion.' },
            ],
          },
          audit: { consistency_status: 'pass', issues: [] },
          provenance: {},
          created_at: '2026-04-11T12:08:00',
          updated_at: '2026-04-11T12:08:00',
        },
      ]
      return { data: { success: true, data: {} } }
    }),
    generatePosterStarter: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
  }
})

vi.mock('@/stores/debug', () => ({
  useDebugStore: () => ({
    logRequest: vi.fn(() => 1),
    resolveRequest: vi.fn(),
    rejectRequest: vi.fn(),
  }),
}))

describe('VisualizationStudio', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    fixtureState.artifactsState = fixtureState.cloneArtifacts()
    vi.mocked(paperLabApi.listVisualizationArtifacts).mockImplementation(async () => ({
      data: {
        success: true,
        data: fixtureState.artifactsState,
      },
    }) as Awaited<ReturnType<typeof paperLabApi.listVisualizationArtifacts>>)
  })

  it('shows export blockers for not-ready artifacts', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()
    const exportButton = wrapper.findAll('button').find(node => node.text().includes('Export'))
    expect(exportButton).toBeTruthy()
    await exportButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Export blockers:')
    expect(wrapper.text()).toContain('Confirm data values')
  })

  it('runs refinement and grounded literature actions', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()

    const refineButton = wrapper.findAll('button').find(node => node.text().includes('Refine Section'))
    expect(refineButton).toBeTruthy()
    await refineButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Refined intro.')

    const litButton = wrapper.findAll('button').find(node => node.text().includes('Find Verified Citations'))
    expect(litButton).toBeTruthy()
    await litButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('All suggested citations are verified.')
    expect(paperLabApi.groundedLiteratureReview).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Draft History')
    expect(wrapper.text()).toContain('Methods')
    expect(wrapper.text()).toContain('battery benchmark')

    const applyButton = wrapper.findAll('button').find(node => node.text().includes('Apply to Draft'))
    expect(applyButton).toBeTruthy()
    await applyButton!.trigger('click')
    await flushPromises()
    expect(paperLabApi.applyPaperRefinement).toHaveBeenCalled()
    expect(paperLabApi.getDraftHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Applied refinement to Introduction')
    expect(wrapper.text()).toContain('applied to draft')

    const revertButton = wrapper.findAll('button').find(node => node.text().includes('Revert'))
    expect(revertButton).toBeTruthy()
    await revertButton!.trigger('click')
    await flushPromises()
    expect(paperLabApi.revertPaperRefinement).toHaveBeenCalledWith('paper_1', 'refine_0')
    expect(wrapper.text()).toContain('Reverted refinement refine_0')
    expect(wrapper.text()).toContain('Restored draft snapshot')
  })

  it('saves artifact edits from the detail workspace', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()
    await wrapper.find('.artifact-card__main').trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('input')
    const titleInput = inputs.find(node => (node.element as HTMLInputElement).value === 'Figure 2')
    expect(titleInput).toBeTruthy()
    await titleInput!.setValue('Figure 2 Updated')

    const select = wrapper.find('select')
    await select.setValue('user_supplied')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('')

    const descriptionArea = wrapper.findAll('textarea').find(node =>
      node.attributes('placeholder')?.includes('Describe what this artifact should communicate'),
    )
    expect(descriptionArea).toBeTruthy()
    await descriptionArea!.setValue('Updated communication goal')

    const selects = wrapper.findAll('select')
    const chartMarkSelect = selects.find(node => node.findAll('option').some(option => option.text() === 'Line'))
    expect(chartMarkSelect).toBeTruthy()
    await chartMarkSelect!.setValue('line')

    const xField = wrapper.find('input[placeholder="e.g. condition"]')
    await xField.setValue('timepoint')
    const yField = wrapper.find('input[placeholder="e.g. performance"]')
    await yField.setValue('capacity')
    const colorField = wrapper.find('input[placeholder="optional grouping field"]')
    await colorField.setValue('cohort')

    const saveButton = wrapper.findAll('button').find(node => node.text().includes('Save Artifact'))
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(paperLabApi.updateVisualizationArtifact).toHaveBeenCalled()
    expect(vi.mocked(paperLabApi.updateVisualizationArtifact).mock.calls[0]?.[2]).toMatchObject({
      title: 'Figure 2 Updated',
      status: 'draft',
      payload: {
        assumptions: [],
        content_description: 'Updated communication goal',
        data_contract: { mode: 'user_supplied' },
        rendering: {
          spec: {
            mark: 'line',
            encoding: {
              x: { field: 'timepoint', type: 'nominal' },
              y: { field: 'capacity', type: 'quantitative' },
              color: { field: 'cohort', type: 'nominal' },
            },
          },
        },
      },
    })
    expect(wrapper.text()).toContain('Saved Figure 2 Updated')
  })

  it('filters inventory and previews slide starter artifacts', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()

    const search = wrapper.find('input[placeholder="Search artifacts"]')
    await search.setValue('slide')
    await flushPromises()
    expect(wrapper.text()).toContain('Slide Starter')
    expect(wrapper.text()).not.toContain('Figure 2')

    const slideMain = wrapper.findAll('.artifact-card__main').find(node => node.text().includes('Slide Starter'))
    expect(slideMain).toBeTruthy()
    await slideMain!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Slide 1')
    expect(wrapper.text()).toContain('Summarize the problem.')
  })

  it('auto-selects newly generated communication outputs', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()

    const slideStarterButton = wrapper.findAll('button').find(node => node.text().includes('Slide Starter'))
    expect(slideStarterButton).toBeTruthy()
    await slideStarterButton!.trigger('click')
    await flushPromises()

    expect(paperLabApi.generateSlideStarter).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Generated scientific slide starter')
    expect(wrapper.text()).toContain('Scientific Slide Starter')
    expect(wrapper.text()).toContain('Frame the research problem.')
  })

  it('saves edited slide content back into the artifact payload', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()

    const slideMain = wrapper.findAll('.artifact-card__main').find(node => node.text().includes('Slide Starter'))
    expect(slideMain).toBeTruthy()
    await slideMain!.trigger('click')
    await flushPromises()

    const textareas = wrapper.findAll('textarea')
    const slidesArea = textareas.find(node => node.attributes('placeholder')?.includes('One slide per line'))
    expect(slidesArea).toBeTruthy()
    await slidesArea!.setValue('Problem: Updated problem framing\nResults: Updated result summary')

    const saveButton = wrapper.findAll('button').find(node => node.text().includes('Save Artifact'))
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(vi.mocked(paperLabApi.updateVisualizationArtifact).mock.calls.at(-1)?.[2]).toMatchObject({
      payload: {
        slides: [
          { title: 'Problem', summary: 'Updated problem framing' },
          { title: 'Results', summary: 'Updated result summary' },
        ],
      },
    })
  })

  it('shows readiness, confidence, and provenance details in the workspace', async () => {
    const wrapper = mount(VisualizationStudio, {
      props: { uploadId: 'paper_1' },
      global: {
        stubs: {
          VisualizationPanel: true,
        },
      },
    })

    await flushPromises()
    await wrapper.find('.artifact-card__main').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Readiness: blocked')
    expect(wrapper.text()).toContain('Confidence: 74%')
    expect(wrapper.text()).toContain('Provenance Details')
    expect(wrapper.text()).toContain('paper_orchestra_service')
    expect(wrapper.text()).toContain('Source refs: Figure 2')
    expect(wrapper.text()).toContain('Linked findings: Clarify statistical significance')
  })
})
