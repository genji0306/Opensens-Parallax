/**
 * Tests for P-2 Knowledge Engine and P-3 Review Board API types + contracts.
 */

import { describe, it, expect } from 'vitest'
import type {
  KnowledgeArtifact,
  ClaimGraphData,
  NoveltyMapData,
  RevisionRound,
} from '@/api/ais'

// ── P-2 Knowledge Types ──────────────────────────────────────────────

describe('P-2 Knowledge Engine Types', () => {
  const MOCK_ARTIFACT: KnowledgeArtifact = {
    artifact_id: 'ka_abc123',
    run_id: 'run_1',
    research_idea: 'EIS + ML for battery monitoring',
    claims: [
      {
        claim_id: 'cl_1',
        text: 'EIS outperforms DC methods',
        category: 'finding',
        confidence: 0.85,
        supporting: ['ev_1'],
        contradicting: [],
        extending: [],
      },
      {
        claim_id: 'cl_2',
        text: 'Transfer learning reduces data needs',
        category: 'method',
        confidence: 0.9,
        supporting: ['ev_2'],
        contradicting: ['ev_3'],
        extending: [],
      },
    ],
    evidence: [
      { evidence_id: 'ev_1', source_type: 'paper', source_id: 'p1', title: 'EIS Review', excerpt: 'Impedance...', confidence: 0.8 },
      { evidence_id: 'ev_2', source_type: 'paper', source_id: 'p2', title: 'Transfer Learning', excerpt: 'TL reduces...', confidence: 0.7 },
      { evidence_id: 'ev_3', source_type: 'debate', source_id: 'sim1', title: 'Debate Turn', excerpt: 'However...', confidence: 0.5 },
    ],
    gaps: [
      { gap_id: 'gap_1', description: 'No long-term data', severity: 'critical', related_claims: ['cl_1'], suggested_approach: 'Run 6-month study', evidence_needed: 'Longitudinal degradation data' },
    ],
    novelty_assessments: [
      { claim_id: 'cl_1', novelty_score: 0.8, explanation: 'Novel combination', closest_existing: ['Paper A'], differentiators: ['Real-time'] },
    ],
    sub_questions: [
      { question_id: 'sq_1', text: 'How does EIS compare?', parent_id: null, evidence_coverage: 0.7, related_claims: ['cl_1'] },
    ],
    hypothesis: {
      hypothesis_id: 'hyp_1',
      problem_statement: 'Battery monitoring lacks real-time capability',
      contribution: 'Combined EIS+ML approach',
      differentiators: ['Real-time', 'Multi-chemistry'],
      predicted_impact: 'Improved BMS',
      supporting_gaps: ['gap_1'],
      novelty_basis: ['cl_1'],
    },
    argument_skeleton: [
      { section_id: 'sec_0', heading: 'Introduction', purpose: 'Set context', key_points: ['Problem'], assigned_citations: ['Paper A'], order: 0 },
    ],
    created_at: '2026-03-29T10:00:00',
    updated_at: '2026-03-29T10:00:00',
  }

  it('KnowledgeArtifact has correct structure', () => {
    expect(MOCK_ARTIFACT.artifact_id).toBe('ka_abc123')
    expect(MOCK_ARTIFACT.claims).toHaveLength(2)
    expect(MOCK_ARTIFACT.evidence).toHaveLength(3)
    expect(MOCK_ARTIFACT.gaps).toHaveLength(1)
    expect(MOCK_ARTIFACT.hypothesis).not.toBeNull()
    expect(MOCK_ARTIFACT.hypothesis?.differentiators).toHaveLength(2)
  })

  it('Claims have typed evidence links', () => {
    const claim = MOCK_ARTIFACT.claims[0]!
    expect(claim.supporting).toContain('ev_1')
    expect(claim.category).toBe('finding')
    expect(claim.confidence).toBeGreaterThan(0)
  })

  it('Gaps reference related claims', () => {
    const gap = MOCK_ARTIFACT.gaps[0]!
    expect(gap.related_claims).toContain('cl_1')
    expect(gap.severity).toBe('critical')
  })

  it('Novelty assessment has score and explanation', () => {
    const na = MOCK_ARTIFACT.novelty_assessments[0]!
    expect(na.novelty_score).toBeGreaterThanOrEqual(0)
    expect(na.novelty_score).toBeLessThanOrEqual(1)
    expect(na.explanation).toBeTruthy()
  })

  it('Hypothesis links to gaps and novelty', () => {
    const hyp = MOCK_ARTIFACT.hypothesis!
    expect(hyp.supporting_gaps).toContain('gap_1')
    expect(hyp.novelty_basis).toContain('cl_1')
    expect(hyp.problem_statement).toBeTruthy()
    expect(hyp.contribution).toBeTruthy()
  })
})

describe('ClaimGraphData shape', () => {
  const MOCK_GRAPH: ClaimGraphData = {
    nodes: [
      { id: 'cl_1', type: 'claim', label: 'EIS outperforms', full_text: 'Full claim text' },
      { id: 'ev_1', type: 'evidence', label: 'EIS Review', full_text: 'Excerpt' },
      { id: 'gap_1', type: 'gap', label: 'No long-term data', full_text: 'Description' },
    ],
    links: [
      { source: 'ev_1', target: 'cl_1', type: 'supports' },
      { source: 'gap_1', target: 'cl_1', type: 'gap_for' },
    ],
    stats: { claims: 1, evidence: 1, gaps: 1, links: 2 },
  }

  it('has nodes with correct types', () => {
    const types = new Set(MOCK_GRAPH.nodes.map(n => n.type))
    expect(types).toContain('claim')
    expect(types).toContain('evidence')
    expect(types).toContain('gap')
  })

  it('has links with typed edges', () => {
    expect(MOCK_GRAPH.links[0]!.type).toBe('supports')
    expect(MOCK_GRAPH.links[1]!.type).toBe('gap_for')
  })

  it('stats match node counts', () => {
    expect(MOCK_GRAPH.stats.claims).toBe(1)
    expect(MOCK_GRAPH.stats.links).toBe(2)
  })
})

describe('NoveltyMapData shape', () => {
  const MOCK_NOVELTY: NoveltyMapData = {
    assessments: [
      { claim_id: 'cl_1', novelty_score: 0.85, explanation: 'Novel', closest_existing: [], differentiators: ['Speed'] },
      { claim_id: 'cl_2', novelty_score: 0.2, explanation: 'Well-covered', closest_existing: ['Paper B'], differentiators: [] },
    ],
    heatmap: [
      { claim_id: 'cl_1', text: 'EIS outperforms', novelty_score: 0.85, zone: 'novel', explanation: 'Novel combination' },
      { claim_id: 'cl_2', text: 'Transfer learning', novelty_score: 0.2, zone: 'covered', explanation: 'Well-known' },
    ],
    stats: { avg_novelty: 0.53, novel_count: 1, covered_count: 1 },
  }

  it('heatmap items have zone classification', () => {
    expect(MOCK_NOVELTY.heatmap[0]!.zone).toBe('novel')
    expect(MOCK_NOVELTY.heatmap[1]!.zone).toBe('covered')
  })

  it('stats aggregate correctly', () => {
    expect(MOCK_NOVELTY.stats.novel_count).toBe(1)
    expect(MOCK_NOVELTY.stats.covered_count).toBe(1)
  })
})

// ── P-3 Review Types ─────────────────────────────────────────────────

describe('P-3 Review Board Types', () => {
  const MOCK_ROUND: RevisionRound = {
    round_id: 'rr_abc',
    run_id: 'run_1',
    round_number: 1,
    rewrite_mode: 'conservative',
    reviewer_types: ['methodological', 'novelty', 'harsh_editor'],
    results: [
      {
        reviewer_type: 'methodological',
        reviewer_name: 'Methodological Reviewer',
        overall_score: 6.5,
        summary: 'Needs stronger controls',
        comments: [
          {
            comment_id: 'rc_1',
            reviewer_type: 'methodological',
            section: 'Methods',
            text: 'Missing control experiment',
            severity: 'critical',
            confidence: 0.9,
            impact: 'high',
            category: 'missing_control',
            quote: 'We compared...',
          },
        ],
        strengths: ['Novel approach'],
        weaknesses: ['Weak controls'],
      },
      {
        reviewer_type: 'novelty',
        reviewer_name: 'Novelty Reviewer',
        overall_score: 8.0,
        summary: 'Strong novelty',
        comments: [],
        strengths: ['Original combination'],
        weaknesses: [],
      },
    ],
    themes: [
      {
        theme_id: 'th_1',
        title: 'Experimental Controls',
        description: 'Add proper control experiments',
        priority: 1,
        impact: 'high',
        comment_ids: ['rc_1'],
        suggested_action: 'Add ablation study',
      },
    ],
    conflicts: [
      {
        conflict_id: 'cf_1',
        reviewer_a: 'methodological',
        reviewer_b: 'novelty',
        description: 'Disagree on experimental scope',
        resolution_suggestion: 'Add targeted experiments',
      },
    ],
    avg_score: 7.25,
    created_at: '2026-03-29T12:00:00',
  }

  it('RevisionRound has correct structure', () => {
    expect(MOCK_ROUND.round_number).toBe(1)
    expect(MOCK_ROUND.rewrite_mode).toBe('conservative')
    expect(MOCK_ROUND.results).toHaveLength(2)
    expect(MOCK_ROUND.themes).toHaveLength(1)
    expect(MOCK_ROUND.conflicts).toHaveLength(1)
  })

  it('ReviewerResult has scored comments', () => {
    const result = MOCK_ROUND.results[0]!
    expect(result.overall_score).toBe(6.5)
    expect(result.comments).toHaveLength(1)
    expect(result.comments[0]!.severity).toBe('critical')
    expect(result.comments[0]!.confidence).toBe(0.9)
    expect(result.comments[0]!.impact).toBe('high')
  })

  it('RevisionTheme links to comments', () => {
    const theme = MOCK_ROUND.themes[0]!
    expect(theme.comment_ids).toContain('rc_1')
    expect(theme.priority).toBe(1)
    expect(theme.impact).toBe('high')
  })

  it('ReviewConflict identifies opposing reviewers', () => {
    const cf = MOCK_ROUND.conflicts[0]!
    expect(cf.reviewer_a).toBe('methodological')
    expect(cf.reviewer_b).toBe('novelty')
    expect(cf.resolution_suggestion).toBeTruthy()
  })

  it('Average score computed from results', () => {
    const scores = MOCK_ROUND.results.map(r => r.overall_score)
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length
    expect(MOCK_ROUND.avg_score).toBe(7.25)
    expect(avg).toBe(7.25)
  })
})

// ── Stage Settings Types ─────────────────────────────────────────────

describe('Stage Settings Schema', () => {
  it('all 9 stages have schemas', async () => {
    const { STAGE_SETTINGS_SCHEMAS } = await import('@/types/stage-settings')
    const stageIds = ['crawl', 'map', 'ideas', 'debate', 'validate', 'draft', 'experiment', 'rehab', 'pass']
    for (const id of stageIds) {
      expect(STAGE_SETTINGS_SCHEMAS[id as keyof typeof STAGE_SETTINGS_SCHEMAS]).toBeDefined()
    }
  })

  it('crawl schema has sources multi-select and max_papers slider', async () => {
    const { STAGE_SETTINGS_SCHEMAS } = await import('@/types/stage-settings')
    const crawl = STAGE_SETTINGS_SCHEMAS.crawl
    const sources = crawl.fields.find(f => f.key === 'sources')
    expect(sources).toBeDefined()
    expect(sources!.type).toBe('multi-select')
    expect(sources!.options!.length).toBeGreaterThan(3)

    const maxPapers = crawl.fields.find(f => f.key === 'max_papers')
    expect(maxPapers).toBeDefined()
    expect(maxPapers!.type).toBe('number')
    expect(maxPapers!.min).toBe(10)
  })

  it('rehab schema has min_score and max_revisions', async () => {
    const { STAGE_SETTINGS_SCHEMAS } = await import('@/types/stage-settings')
    const rehab = STAGE_SETTINGS_SCHEMAS.rehab
    expect(rehab.fields.find(f => f.key === 'min_score')).toBeDefined()
    expect(rehab.fields.find(f => f.key === 'max_revisions')).toBeDefined()
  })

  it('getDefaultSettings returns valid defaults', async () => {
    const { getDefaultSettings } = await import('@/types/stage-settings')
    const defaults = getDefaultSettings('crawl')
    expect(defaults.sources).toBeDefined()
    expect(Array.isArray(defaults.sources)).toBe(true)
    expect(defaults.max_papers).toBe(100)
  })

  it('pass stage has no settings fields', async () => {
    const { STAGE_SETTINGS_SCHEMAS } = await import('@/types/stage-settings')
    expect(STAGE_SETTINGS_SCHEMAS.pass.fields).toHaveLength(0)
  })
})

// ── Pipeline Store Graph Overlay ─────────────────────────────────────

describe('Pipeline Store Graph Integration', () => {
  it('exports graph-related functions', async () => {
    const { usePipelineStore } = await import('@/stores/pipeline')
    const { setActivePinia, createPinia } = await import('pinia')
    setActivePinia(createPinia())

    const store = usePipelineStore()
    expect(typeof store.fetchAndOverlayGraph).toBe('function')
    expect(typeof store.getGraphNodeForStage).toBe('function')
    expect(store.graphNodes).toEqual([])
  })

  it('clearProject resets graphNodes', async () => {
    const { usePipelineStore } = await import('@/stores/pipeline')
    const { setActivePinia, createPinia } = await import('pinia')
    setActivePinia(createPinia())

    const store = usePipelineStore()
    store.clearProject()
    expect(store.graphNodes).toEqual([])
    expect(store.activeRunId).toBeNull()
  })
})
