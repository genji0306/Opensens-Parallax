/**
 * BFTSTreeView + ExperimentDetail V2 Mode Tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('axios', () => {
  const instance = {
    get: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    post: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    put: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
    delete: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
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

import type { BFTSTreeStructure, BFTSNode } from '@/api/ais'

const MOCK_TREE: BFTSTreeStructure = {
  nodes: [
    { node_id: 'root', parent_id: null, depth: 0, status: 'success', metrics: { loss: 0.45 }, code_changes: '', is_best: false },
    { node_id: 'n1', parent_id: 'root', depth: 1, status: 'success', metrics: { loss: 0.32, accuracy: 0.85 }, code_changes: '', is_best: true },
    { node_id: 'n2', parent_id: 'root', depth: 1, status: 'failed', metrics: {}, code_changes: '', is_best: false },
    { node_id: 'n3', parent_id: 'n1', depth: 2, status: 'success', metrics: { loss: 0.28 }, code_changes: '', is_best: false },
  ],
  max_depth: 2,
  total_explored: 4,
  successful: 3,
  failed: 1,
  best_node_id: 'n1',
  best_metrics: { loss: 0.32, accuracy: 0.85 },
}

describe('BFTSTreeView', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  it('mounts and renders tree summary metrics', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    expect(wrapper.exists()).toBe(true)
    // Should render 5 MetricCards (Explored, Successful, Failed, Max Depth, Success Rate)
    const metricCards = wrapper.findAllComponents({ name: 'MetricCard' })
    expect(metricCards.length).toBe(5)
  })

  it('highlights the best node', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const bestSection = wrapper.find('.bfts-tree__best')
    expect(bestSection.exists()).toBe(true)
    expect(bestSection.text()).toContain('n1')
  })

  it('renders SVG with correct number of node circles', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const circles = wrapper.findAll('.bfts-tree__svg circle')
    expect(circles.length).toBe(4)
  })

  it('renders SVG edges connecting parent/child nodes', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const lines = wrapper.findAll('.bfts-tree__svg line')
    // root→n1, root→n2, n1→n3 = 3 edges
    expect(lines.length).toBe(3)
  })

  it('renders node list with all nodes', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const listItems = wrapper.findAll('.bfts-tree__list-item')
    expect(listItems.length).toBe(4)
  })

  it('marks best node in list with badge', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const bestItems = wrapper.findAll('.bfts-tree__list-item--best')
    expect(bestItems.length).toBe(1)
    expect(bestItems[0]!.text()).toContain('best')
  })

  it('emits select-node on node click', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    const listItems = wrapper.findAll('.bfts-tree__list-item')
    await listItems[1]!.trigger('click')
    const emitted = wrapper.emitted('select-node')
    expect(emitted).toBeTruthy()
    expect(emitted!.length).toBe(1)
    expect((emitted![0]![0] as BFTSNode).node_id).toBe('n1')
  })

  it('handles empty tree gracefully', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const emptyTree: BFTSTreeStructure = {
      nodes: [], max_depth: 0, total_explored: 0,
      successful: 0, failed: 0, best_node_id: null, best_metrics: {},
    }
    const wrapper = mount(BFTSTreeView, { props: { tree: emptyTree } })
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.bfts-tree__best').exists()).toBe(false)
  })

  it('calculates success rate correctly', async () => {
    const BFTSTreeView = (await import('@/components/stages/BFTSTreeView.vue')).default
    const wrapper = mount(BFTSTreeView, { props: { tree: MOCK_TREE } })
    // 3/4 = 75%
    expect(wrapper.text()).toContain('75%')
  })
})

describe('ExperimentDetail V2 mode', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  it('detects V2 result and shows BFTS badge', async () => {
    const ExperimentDetail = (await import('@/components/stages/ExperimentDetail.vue')).default
    const wrapper = mount(ExperimentDetail, {
      props: {
        result: {
          status: 'completed',
          is_v2: true,
          tree_structure: MOCK_TREE,
          token_usage: { total_input_tokens: 50000, total_output_tokens: 15000, total_cost_usd: 5.0, by_model: {} },
          self_review: 'Good paper.',
        },
      },
    })
    expect(wrapper.find('.v2-badge').exists()).toBe(true)
    expect(wrapper.text()).toContain('V2')
  })

  it('renders BFTSTreeView for V2 results', async () => {
    const ExperimentDetail = (await import('@/components/stages/ExperimentDetail.vue')).default
    const wrapper = mount(ExperimentDetail, {
      props: {
        result: {
          status: 'completed',
          is_v2: true,
          tree_structure: MOCK_TREE,
          token_usage: { total_input_tokens: 0, total_output_tokens: 0, total_cost_usd: 0, by_model: {} },
        },
      },
    })
    const tree = wrapper.findComponent({ name: 'BFTSTreeView' })
    expect(tree.exists()).toBe(true)
  })

  it('shows V2 cost breakdown', async () => {
    const ExperimentDetail = (await import('@/components/stages/ExperimentDetail.vue')).default
    const wrapper = mount(ExperimentDetail, {
      props: {
        result: {
          status: 'completed',
          is_v2: true,
          tree_structure: MOCK_TREE,
          token_usage: {
            total_input_tokens: 50000,
            total_output_tokens: 15000,
            total_cost_usd: 5.25,
            by_model: { 'claude-sonnet': { input_tokens: 50000, output_tokens: 15000, cost_usd: 5.25 } },
          },
        },
      },
    })
    expect(wrapper.find('.v2-cost-section').exists()).toBe(true)
    expect(wrapper.text()).toContain('$5.25')
  })

  it('shows self-review for V2 results', async () => {
    const ExperimentDetail = (await import('@/components/stages/ExperimentDetail.vue')).default
    const wrapper = mount(ExperimentDetail, {
      props: {
        result: {
          status: 'completed',
          is_v2: true,
          tree_structure: MOCK_TREE,
          token_usage: { total_input_tokens: 0, total_output_tokens: 0, total_cost_usd: 0, by_model: {} },
          self_review: 'Promising experimental results.',
        },
      },
    })
    expect(wrapper.find('.v2-review-section').exists()).toBe(true)
    expect(wrapper.text()).toContain('Promising experimental results')
  })

  it('does NOT show V2 elements for V1 results', async () => {
    const ExperimentDetail = (await import('@/components/stages/ExperimentDetail.vue')).default
    const wrapper = mount(ExperimentDetail, {
      props: {
        result: {
          status: 'completed',
          template: 'nanoGPT',
          final_loss: 0.35,
        },
      },
    })
    expect(wrapper.find('.v2-badge').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'BFTSTreeView' }).exists()).toBe(false)
  })
})
