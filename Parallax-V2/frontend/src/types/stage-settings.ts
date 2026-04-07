/**
 * Typed settings schemas per pipeline stage (Sprint 4, Task 4.1).
 *
 * Each stage has a typed schema defining user-configurable parameters.
 * The StageSettingsForm component renders dynamic controls from these schemas.
 */

import type { StageId } from './pipeline'

export type SettingType = 'number' | 'boolean' | 'select' | 'multi-select' | 'text'

export interface SettingField {
  key: string
  label: string
  type: SettingType
  description?: string
  default: unknown
  /** For number: min/max/step */
  min?: number
  max?: number
  step?: number
  /** For select/multi-select: available options */
  options?: Array<{ value: string; label: string }>
}

export interface StageSettingsSchema {
  stageId: StageId
  label: string
  fields: SettingField[]
}

// ── Per-Stage Schemas ────────────────────────────────────────────────

const SEARCH_SOURCES = [
  { value: 'arxiv', label: 'arXiv' },
  { value: 'semantic_scholar', label: 'Semantic Scholar' },
  { value: 'openalex', label: 'OpenAlex' },
  { value: 'crossref', label: 'CrossRef' },
  { value: 'pubmed', label: 'PubMed' },
  { value: 'core', label: 'CORE' },
  { value: 'doaj', label: 'DOAJ' },
  { value: 'europe_pmc', label: 'Europe PMC' },
]

const SPECIALIST_DOMAINS = [
  { value: 'electrochemistry', label: 'Electrochemistry' },
  { value: 'eis', label: 'EIS' },
  { value: 'spectroscopy', label: 'Spectroscopy' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'statistics', label: 'Statistics' },
  { value: 'ml_methodology', label: 'ML Methodology' },
  { value: 'energy_systems', label: 'Energy Systems' },
  { value: 'reproducibility', label: 'Reproducibility' },
]

export const STAGE_SETTINGS_SCHEMAS: Record<StageId, StageSettingsSchema> = {
  crawl: {
    stageId: 'crawl',
    label: 'Literature Search Settings',
    fields: [
      {
        key: 'sources',
        label: 'Sources',
        type: 'multi-select',
        description: 'Academic databases to search',
        default: ['arxiv', 'semantic_scholar', 'openalex'],
        options: SEARCH_SOURCES,
      },
      {
        key: 'max_papers',
        label: 'Max Papers',
        type: 'number',
        description: 'Maximum number of papers to ingest',
        default: 100,
        min: 10,
        max: 500,
        step: 10,
      },
    ],
  },
  map: {
    stageId: 'map',
    label: 'Topic Mapping Settings',
    fields: [
      {
        key: 'clustering',
        label: 'Clustering Method',
        type: 'select',
        default: 'llm_assisted',
        options: [
          { value: 'llm_assisted', label: 'LLM-Assisted' },
          { value: 'keyword', label: 'Keyword-Based' },
        ],
      },
      {
        key: 'citation_graph',
        label: 'Citation Graph',
        type: 'boolean',
        description: 'Include citation relationships in topic map',
        default: true,
      },
    ],
  },
  ideas: {
    stageId: 'ideas',
    label: 'Idea Generation Settings',
    fields: [
      {
        key: 'num_ideas',
        label: 'Number of Ideas',
        type: 'number',
        default: 10,
        min: 3,
        max: 30,
        step: 1,
      },
      {
        key: 'num_reflections',
        label: 'Reflection Rounds',
        type: 'number',
        description: 'LLM self-reflection iterations for idea quality',
        default: 3,
        min: 1,
        max: 5,
        step: 1,
      },
    ],
  },
  debate: {
    stageId: 'debate',
    label: 'Agent Debate Settings',
    fields: [
      {
        key: 'max_rounds',
        label: 'Max Rounds',
        type: 'number',
        default: 5,
        min: 2,
        max: 15,
        step: 1,
      },
      {
        key: 'agents',
        label: 'Agent Count',
        type: 'number',
        default: 6,
        min: 3,
        max: 12,
        step: 1,
      },
      {
        key: 'format',
        label: 'Debate Format',
        type: 'select',
        default: 'adversarial',
        options: [
          { value: 'adversarial', label: 'Adversarial' },
          { value: 'collaborative', label: 'Collaborative' },
          { value: 'structured', label: 'Structured' },
        ],
      },
    ],
  },
  validate: {
    stageId: 'validate',
    label: 'Validation Settings',
    fields: [
      {
        key: 'novelty_check',
        label: 'Novelty Check',
        type: 'boolean',
        default: true,
      },
      {
        key: 'citation_verify',
        label: 'Citation Verification',
        type: 'boolean',
        default: true,
      },
      {
        key: 'specialist_domains',
        label: 'Specialist Domains',
        type: 'multi-select',
        description: 'Domain experts to include in review',
        default: [],
        options: SPECIALIST_DOMAINS,
      },
    ],
  },
  draft: {
    stageId: 'draft',
    label: 'Paper Draft Settings',
    fields: [
      {
        key: 'paper_format',
        label: 'Paper Format',
        type: 'select',
        default: 'ieee',
        options: [
          { value: 'ieee', label: 'IEEE' },
          { value: 'acm', label: 'ACM' },
          { value: 'nature', label: 'Nature' },
          { value: 'apa', label: 'APA' },
        ],
      },
      {
        key: 'sections',
        label: 'Sections',
        type: 'select',
        description: 'Section layout for the paper',
        default: 'auto',
        options: [
          { value: 'auto', label: 'Auto-detect' },
          { value: 'standard', label: 'Standard (Intro/Method/Results/Discussion)' },
          { value: 'extended', label: 'Extended (+ Related Work, Limitations)' },
        ],
      },
    ],
  },
  experiment: {
    stageId: 'experiment',
    label: 'Experiment Design Settings',
    fields: [
      {
        key: 'ais_version',
        label: 'AI Scientist Version',
        type: 'select',
        description: 'V1 uses templates; V2 uses agentic tree search (BFTS)',
        default: 'v2',
        options: [
          { value: 'v1', label: 'V1 (Template-based)' },
          { value: 'v2', label: 'V2 (Tree Search / BFTS)' },
        ],
      },
      {
        key: 'bfts_profile',
        label: 'Exploration Depth',
        type: 'select',
        description: 'BFTS profile (V2 only)',
        default: 'standard',
        options: [
          { value: 'quick', label: 'Quick (3 steps, ~$10)' },
          { value: 'standard', label: 'Standard (5 steps, ~$25)' },
          { value: 'thorough', label: 'Thorough (10 steps, ~$40)' },
        ],
      },
      {
        key: 'include_writeup',
        label: 'Generate Paper',
        type: 'boolean',
        description: 'V2 can generate a full 4-page paper (~$5 extra)',
        default: false,
      },
      {
        key: 'auto_detect_gaps',
        label: 'Auto-detect Gaps',
        type: 'boolean',
        description: 'Automatically identify evidence gaps from draft',
        default: true,
      },
      {
        key: 'required',
        label: 'Required',
        type: 'boolean',
        description: 'Force experiment stage (skip if false and no gaps found)',
        default: false,
      },
    ],
  },
  rehab: {
    stageId: 'rehab',
    label: 'Revision Settings',
    fields: [
      {
        key: 'min_score',
        label: 'Minimum Pass Score',
        type: 'number',
        description: 'Score threshold to pass without revision loop',
        default: 6.0,
        min: 1,
        max: 10,
        step: 0.5,
      },
      {
        key: 'max_revisions',
        label: 'Max Revisions',
        type: 'number',
        description: 'Maximum revision loop iterations before failing',
        default: 3,
        min: 1,
        max: 10,
        step: 1,
      },
    ],
  },
  pass: {
    stageId: 'pass',
    label: 'Pass / Publish',
    fields: [],
  },
}

/** Get the settings schema for a stage. */
export function getSettingsSchema(stageId: StageId): StageSettingsSchema {
  return STAGE_SETTINGS_SCHEMAS[stageId]
}

/** Build default settings values from a schema. */
export function getDefaultSettings(stageId: StageId): Record<string, unknown> {
  const schema = STAGE_SETTINGS_SCHEMAS[stageId]
  const defaults: Record<string, unknown> = {}
  for (const field of schema.fields) {
    defaults[field.key] = field.default
  }
  return defaults
}
