<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { PaperUpload } from '@/types/api'
import {
  uploadPaper,
  startReview,
  getUploadStatus,
  getRounds,
  getDraft,
  listUploads,
  runSpecialistReview,
  getSpecialistReview,
  exportDocx,
  getResponseToReviewers,
  getRewriteInstructions,
  subscribeToProgress,
} from '@/api/paperLab'
import { exportDraft } from '@/api/ais'
import GlassPanel from '@/components/shared/GlassPanel.vue'
import ActionButton from '@/components/shared/ActionButton.vue'
import StatusBadge from '@/components/shared/StatusBadge.vue'
import StatusBreadcrumb from '@/components/paper/StatusBreadcrumb.vue'
import ComparativeAnalysisPanel from '@/components/paper/ComparativeAnalysisPanel.vue'
import ReviewOverviewPanel from '@/components/paper/ReviewOverviewPanel.vue'
import VisualizationStudio from '@/components/paper/VisualizationStudio.vue'

const route = useRoute()
const router = useRouter()

// ── Types for rounds data ────────────────────────────────────────────────

interface Weakness {
  severity: string
  section: string
  text: string
  suggestion: string
}

interface LanguageIssue {
  text: string
  suggestion?: string
}

interface Review {
  reviewer: string
  archetype: string
  score: number
  decision: string
  strengths: string[]
  weaknesses: Weakness[]
  language_issues: LanguageIssue[]
}

interface Consolidated {
  avg_overall_score: number
  final_decision: string
  all_weaknesses: Weakness[]
}

interface TriageItem {
  weakness: string
  action: 'accept' | 'rebut' | 'defer'
  justification: string
}

interface Revision {
  triage: TriageItem[]
  accepted_count: number
  rebutted_count: number
  deferred_count: number
}

interface RoundData {
  round: number
  reviews: Review[]
  consolidated: Consolidated
  revision: Revision
}

interface ReviewerProfile {
  name: string
  archetype: string
  affiliation: string
  assertiveness: number
  detail_orientation: number
  focus: string
}

interface SourceAudit {
  verified: string[]
  unverified: string[]
  method: string
}

interface RoundsResponse {
  rounds: RoundData[]
  score_progression: number[]
  reviewers: ReviewerProfile[]
  source_audit: SourceAudit
}

interface DraftResponse {
  title: string
  draft: string
  word_count: number
}

// ── State ───────────────────────────────────────────────────────────────

const uploads = ref<PaperUpload[]>([])
const selectedUpload = ref<PaperUpload | null>(null)
const selectedUploadIds = ref<string[]>([])
const compareMode = ref(false)

const uploading = ref(false)
const reviewing = ref(false)
const importing = ref(false)
const importError = ref<string | null>(null)
const loadingUploads = ref(false)
const uploadsError = ref<string | null>(null)
const dragOver = ref(false)

// Review config
const reviewConfig = ref({
  rounds: 3,
  reviewers: 5,
  authors: 3,
  live: true,
})
const showConfig = ref(false)

// Review progress
const reviewProgress = ref<string>('')
const exportFeedback = ref<string | null>(null)
const inlineNotice = ref<string | null>(null)

// Loaded data
const roundsData = ref<RoundsResponse | null>(null)
const currentDraft = ref<DraftResponse | null>(null)
const loadingUploadDetail = ref(false)

// Expandable round toggles

// Unsubscribe handle for SSE
let unsubscribeSSE: (() => void) | null = null
let activeReviewSessionId: string | undefined

function normalizeUpload(upload: PaperUpload): PaperUpload {
  const scoreProgression = Array.isArray(upload.review_scores)
    ? [...upload.review_scores]
    : Array.isArray(upload.score_progression)
      ? [...upload.score_progression]
      : [
          ...(typeof upload.initial_score === 'number' ? [upload.initial_score] : []),
          ...(typeof upload.final_score === 'number' && upload.final_score !== upload.initial_score
            ? [upload.final_score]
            : []),
        ]

  const roundCount = typeof upload.round_count === 'number'
    ? upload.round_count
    : typeof upload.rounds_completed === 'number'
      ? upload.rounds_completed
      : scoreProgression.length

  return {
    ...upload,
    field: upload.field ?? upload.detected_field ?? 'general',
    detected_field: upload.detected_field ?? upload.field ?? 'general',
    review_scores: scoreProgression,
    score_progression: upload.score_progression ?? scoreProgression,
    round_count: roundCount,
    rounds_completed: upload.rounds_completed ?? roundCount,
    parser_engine: upload.parser_engine ?? 'unknown',
    parser_mode: upload.parser_mode ?? 'unknown',
    parse_quality: upload.parse_quality ?? {},
    ocr_used: upload.ocr_used ?? false,
    document_counts: upload.document_counts ?? {},
    parse_warnings: upload.parse_warnings ?? [],
    parse_quality_breakdown: upload.parse_quality_breakdown ?? upload.parse_quality ?? {},
    sections: upload.sections ?? [],
    tables: upload.tables ?? [],
    figures: upload.figures ?? [],
    formulas: upload.formulas ?? [],
  }
}

function parserLabel(parserEngine?: string | null): string {
  const value = (parserEngine || 'unknown').replace(/[_+]/g, ' ').trim()
  return value ? value.replace(/\b\w/g, (char) => char.toUpperCase()) : 'Unknown'
}

function parseOverallScore(upload: PaperUpload | null | undefined): number | null {
  const overall = upload?.parse_quality?.overall
  return typeof overall === 'number' ? overall : null
}

function parseQualityLabel(upload: PaperUpload | null | undefined): string {
  const overall = parseOverallScore(upload)
  if (overall == null) return 'Unknown'
  if (overall >= 0.85) return 'High'
  if (overall >= 0.65) return 'Medium'
  return 'Low'
}

function parseQualityClass(upload: PaperUpload | null | undefined): string {
  const overall = parseOverallScore(upload)
  if (overall == null) return 'unknown'
  if (overall >= 0.85) return 'good'
  if (overall >= 0.65) return 'warn'
  return 'bad'
}

function formatParseMetric(value: unknown): string {
  return typeof value === 'number' ? value.toFixed(2) : 'n/a'
}

function previewText(value: unknown, maxLength = 180): string {
  if (typeof value !== 'string' || !value.trim()) return 'No preview available'
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > maxLength ? `${compact.slice(0, maxLength - 1)}…` : compact
}

function tablePreview(table: Record<string, unknown>): string {
  return previewText(table.markdown ?? table.html ?? table.title, 220)
}

function figurePreview(figure: Record<string, unknown>): string {
  return previewText(figure.caption ?? figure.title, 180)
}

function formulaPreview(formula: Record<string, unknown>): string {
  return previewText(formula.latex, 160)
}

function pageLabel(entity: Record<string, unknown>): string {
  const page = entity.page
  return typeof page === 'number' && page > 0 ? `Page ${page}` : 'Page n/a'
}

function bboxLabel(entity: Record<string, unknown>): string | null {
  const bbox = entity.bbox
  if (!Array.isArray(bbox) || bbox.length < 4) return null
  const values = bbox.slice(0, 4).map((value) => (
    typeof value === 'number' ? Math.round(value) : value
  ))
  return `bbox ${values.join(', ')}`
}

async function refreshSelectedUpload(uploadId: string) {
  loadingUploadDetail.value = true
  try {
    const res = await getUploadStatus(uploadId)
    const detail = normalizeUpload(res.data?.data as PaperUpload)
    selectedUpload.value = detail
    uploads.value = uploads.value.map((entry) => (
      entry.upload_id === uploadId
        ? { ...entry, ...detail }
        : entry
    ))
  } catch (err) {
    const msg = getApiErrorMessage(err, 'Failed to load manuscript details')
    inlineNotice.value = msg
  } finally {
    loadingUploadDetail.value = false
  }
}

function syncSelectedUploadFromList() {
  if (!selectedUpload.value) return
  const fresh = uploads.value.find((upload) => upload.upload_id === selectedUpload.value?.upload_id)
  if (fresh) {
    selectedUpload.value = fresh
  }
}

function selectUploadById(uploadId?: string | null): boolean {
  if (!uploadId) return false
  const upload = uploads.value.find((entry) => entry.upload_id === uploadId)
  if (!upload) return false
  selectUpload(upload)
  return true
}

function toggleCompare(uploadId: string) {
  const idx = selectedUploadIds.value.indexOf(uploadId)
  if (idx > -1) {
    selectedUploadIds.value.splice(idx, 1)
  } else {
    selectedUploadIds.value.push(uploadId)
  }
}

function findImportedDraftUpload(runId: string): PaperUpload | undefined {
  return uploads.value.find((upload) => upload.source_filename === `draft_${runId}.md`)
}

// ── Computed ────────────────────────────────────────────────────────────

const selectedUploadsFull = computed<PaperUpload[]>(() => {
  return uploads.value.filter(u => selectedUploadIds.value.includes(u.upload_id))
})



function scoreColor(score: number): string {
  if (score >= 7) return 'var(--success)'
  if (score >= 4) return 'var(--warning)'
  return 'var(--error)'
}

function scoreColorHex(score: number): string {
  if (score >= 7) return '#22c55e'
  if (score >= 4) return '#eab308'
  return '#ef4444'
}

function uploadBadgeStatus(status: string): 'done' | 'active' | 'pending' | 'failed' {
  if (['completed', 'review_complete', 'gap_filled', 'specialist_complete'].includes(status)) return 'done'
  if (['reviewing', 'specialist_running'].includes(status)) return 'active'
  if (status === 'review_failed') return 'failed'
  return 'pending'
}

/** True when the upload is in a "ready to review" initial state */
function isReadyForReview(status: string): boolean {
  return ['uploaded', 'parsed', 'pending'].includes(status)
}

/** True when review process has completed (any terminal status) */
function isReviewComplete(status: string): boolean {
  return ['completed', 'review_complete', 'gap_filled', 'specialist_complete'].includes(status)
}



// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(async () => {
  await fetchUploads()
  await syncRouteState()

  const qUploads = route.query.uploads
  if (qUploads && typeof qUploads === 'string') {
    selectedUploadIds.value = qUploads.split(',')
    compareMode.value = true
  }
})

watch([selectedUploadIds, compareMode], () => {
  const q = { ...route.query }
  if (compareMode.value && selectedUploadIds.value.length > 0) {
    q.uploads = selectedUploadIds.value.join(',')
    delete q.upload_id
  } else {
    delete q.uploads
    if (selectedUpload.value?.upload_id) {
      q.upload_id = selectedUpload.value.upload_id
    }
  }
  router.replace({ query: q })
})

watch(
  () => [route.query.upload_id, route.query.run_id],
  async () => {
    await syncRouteState()
  },
)

onUnmounted(() => {
  if (unsubscribeSSE) {
    unsubscribeSSE()
    unsubscribeSSE = null
  }
})

// ── Actions ─────────────────────────────────────────────────────────────

function getApiErrorMessage(err: unknown, fallback = 'Request failed'): string {
  if (err instanceof Error && err.message) {
    const maybeAxios = err as Error & {
      response?: {
        data?: {
          error?: string
          message?: string
        }
      }
    }
    const apiMsg = maybeAxios.response?.data?.error || maybeAxios.response?.data?.message
    if (apiMsg) return apiMsg
    return err.message
  }
  return fallback
}

function pushSelectionToRoute(uploadId: string | null) {
  const query = { ...route.query }
  if (uploadId) {
    query.upload_id = uploadId
  } else {
    delete query.upload_id
  }
  if (!compareMode.value) {
    delete query.uploads
  }
  router.replace({ query })
}

async function fetchUploads() {
  loadingUploads.value = true
  uploadsError.value = null
  try {
    const res = await listUploads()
    const payload = res.data?.data
    if (Array.isArray(payload)) {
      uploads.value = (payload as PaperUpload[]).map(normalizeUpload)
    } else if (payload && typeof payload === 'object' && 'items' in payload) {
      uploads.value = ((((payload as { items?: PaperUpload[] }).items) ?? []) as PaperUpload[]).map(normalizeUpload)
    } else {
      uploads.value = []
    }
    syncSelectedUploadFromList()
  } catch (err) {
    const msg = getApiErrorMessage(err, 'Failed to load uploads')
    if (msg.includes('Network Error') || msg.includes('timeout')) {
      uploadsError.value = 'Backend offline'
    } else {
      uploadsError.value = msg
    }
  } finally {
    loadingUploads.value = false
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}

function handleDragLeave() {
  dragOver.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer?.files
  const file = files?.[0]
  if (file) {
    handleFileUpload(file)
  }
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    handleFileUpload(file)
  }
}

async function handleFileUpload(file: File): Promise<string | null> {
  const validTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'text/markdown',
  ]
  const validExtensions = ['.pdf', '.doc', '.docx', '.txt', '.md', '.markdown']
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

  if (!validTypes.includes(file.type) && !validExtensions.includes(ext)) {
    inlineNotice.value = 'Please upload a .pdf, .doc, .docx, .txt, .md, or .markdown file.'
    return null
  }

  uploading.value = true
  try {
    const res = await uploadPaper(file)
    const uploadId = res.data?.data?.upload_id
    if (uploadId) {
      await fetchUploads()
      const newUpload = uploads.value.find((u) => u.upload_id === uploadId)
      if (newUpload) {
        selectUpload(newUpload)
      }
      inlineNotice.value = 'Upload complete. Review-ready manuscript selected.'
      return uploadId
    }
  } catch (err) {
    const msg = getApiErrorMessage(err, 'Upload failed')
    uploadsError.value = `Upload failed: ${msg}`
    console.error('Upload failed:', msg, err)
    inlineNotice.value = `Upload failed: ${msg}`
  } finally {
    uploading.value = false
  }
  return null
}

function selectUpload(upload: PaperUpload) {
  // Disconnect previous SSE
  if (unsubscribeSSE) {
    unsubscribeSSE()
    unsubscribeSSE = null
  }
  selectedUpload.value = upload
  pushSelectionToRoute(upload.upload_id)
  reviewProgress.value = ''
  roundsData.value = null
  currentDraft.value = null
  inlineNotice.value = null

  refreshSelectedUpload(upload.upload_id)
  // Load rounds + draft if available
  loadRoundsAndDraft(upload.upload_id)
  loadSpecialistSnapshot(upload.upload_id)
}

async function loadRoundsAndDraft(uploadId: string) {
  try {
    const [roundsRes, draftRes] = await Promise.allSettled([
      getRounds(uploadId),
      getDraft(uploadId),
    ])

    if (roundsRes.status === 'fulfilled') {
      const raw = roundsRes.value.data?.data
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        roundsData.value = raw as unknown as RoundsResponse
      } else if (Array.isArray(raw)) {
        // Legacy format: just an array of rounds
        roundsData.value = {
          rounds: raw as unknown as RoundData[],
          score_progression: [],
          reviewers: [],
          source_audit: { verified: [], unverified: [], method: '' },
        }
      }
    }

    if (draftRes.status === 'fulfilled') {
      const raw = draftRes.value.data?.data
      if (raw && typeof raw === 'object') {
        currentDraft.value = raw as unknown as DraftResponse
      }
    }
  } catch {
    // Partial load is fine
  }
}

async function loadSpecialistSnapshot(uploadId: string) {
  specialistResults.value = null
  specialistStatus.value = 'idle'
  try {
    const res = await getSpecialistReview(uploadId)
    if (res.data?.data) {
      specialistResults.value = res.data.data
      specialistStatus.value = 'done'
    }
  } catch {
    specialistStatus.value = 'idle'
  }
}

async function syncRouteState() {
  const uploadId = route.query.upload_id as string | undefined
  if (selectUploadById(uploadId)) {
    return
  }

  const runId = route.query.run_id as string | undefined
  if (!runId) return

  const existingUpload = findImportedDraftUpload(runId)
  if (existingUpload) {
    selectUpload(existingUpload)
    await router.replace({ name: 'paper-lab', query: { upload_id: existingUpload.upload_id } })
    return
  }

  // Bug #9 fix: show progress + error state during auto-import
  importing.value = true
  importError.value = null
  try {
    const res = await exportDraft(runId, 'markdown')
    const markdown = res.data?.data
    if (markdown && typeof markdown === 'string') {
      const blob = new Blob([markdown], { type: 'text/markdown' })
      const file = new File([blob], `draft_${runId}.md`, { type: 'text/markdown' })
      const newUploadId = await handleFileUpload(file)
      if (newUploadId) {
        await router.replace({ name: 'paper-lab', query: { upload_id: newUploadId } })
      }
    } else {
      importError.value = 'No draft available for this pipeline run.'
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    importError.value = `Could not import pipeline draft: ${msg}`
  } finally {
    importing.value = false
  }
}

async function handleStartReview() {
  if (!selectedUpload.value) return
  reviewing.value = true
  reviewProgress.value = 'Starting review...'

  try {
    showConfig.value = false
    const startRes = await startReview(selectedUpload.value.upload_id, {
      rounds: reviewConfig.value.rounds,
      reviewers: reviewConfig.value.reviewers,
      authors: reviewConfig.value.authors,
      live: reviewConfig.value.live,
    })
    activeReviewSessionId = startRes.data?.data?.session_id

    // Subscribe to SSE for progress
    unsubscribeSSE = subscribeToProgress(
      selectedUpload.value.upload_id,
      activeReviewSessionId,
      (event) => {
        switch (event.type) {
          case 'review_start':
            reviewProgress.value = 'Reviewers evaluating manuscript...'
            break
          case 'review_complete':
            reviewProgress.value = 'Review round complete. Revising...'
            break
          case 'revision_start':
            reviewProgress.value = 'Authors revising manuscript...'
            break
          case 'revision_complete':
            reviewProgress.value = 'Revision complete.'
            break
          case 'converged':
            reviewProgress.value = 'Review converged.'
            break
          case 'complete':
            reviewProgress.value = 'Review complete!'
            reviewing.value = false
            fetchUploads()
            if (selectedUpload.value) {
              loadRoundsAndDraft(selectedUpload.value.upload_id)
              loadSpecialistSnapshot(selectedUpload.value.upload_id)
            }
            break
          case 'error':
            reviewProgress.value = 'Review failed.'
            reviewing.value = false
            inlineNotice.value = 'Review failed. Inspect the latest backend error and try again.'
            break
          case 'stream_error':
            reviewProgress.value = 'Live stream disconnected.'
            reviewing.value = false
            inlineNotice.value = 'Live progress connection was lost. Refresh the upload state and retry if needed.'
            break
        }
      },
    )
  } catch (err) {
    console.error('Start review failed:', err)
    reviewing.value = false
    reviewProgress.value = 'Failed to start review.'
    inlineNotice.value = getApiErrorMessage(err, 'Failed to start review.')
  }
}



const runningSpecialist = ref(false)
const specialistResults = ref<Record<string, unknown> | null>(null)
const specialistStatus = ref<'idle' | 'running' | 'done' | 'error'>('idle')
let specialistPollTimer: ReturnType<typeof setTimeout> | null = null

async function pollSpecialistResults(uploadId: string, attempts = 0) {
  if (attempts > 30) { specialistStatus.value = 'error'; return }
  try {
    const res = await getSpecialistReview(uploadId)
    const data = res.data?.data
    if (data && typeof data === 'object' && Object.keys(data).length > 0) {
      specialistResults.value = data as Record<string, unknown>
      specialistStatus.value = 'done'
      return
    }
  } catch { /* still running */ }
  specialistPollTimer = setTimeout(() => pollSpecialistResults(uploadId, attempts + 1), 4000)
}

async function handleSpecialistReview() {
  if (!selectedUpload.value) return
  runningSpecialist.value = true
  specialistResults.value = null
  specialistStatus.value = 'running'
  if (specialistPollTimer) clearTimeout(specialistPollTimer)
  try {
    const res = await runSpecialistReview(selectedUpload.value.upload_id, { target: 'draft' })
    const data = res.data?.data as unknown as Record<string, unknown>
    if (data?.task_id) pollSpecialistResults(selectedUpload.value.upload_id)
    inlineNotice.value = 'Specialist review started.'
  } catch (err) {
    const msg = getApiErrorMessage(err, 'Specialist review failed')
    uploadsError.value = `Specialist review failed: ${msg}`
    specialistStatus.value = 'error'
    console.error('Specialist review failed:', msg, err)
  } finally {
    runningSpecialist.value = false
  }
}

// ── Score Sparkline ──────────────────────────────────────────────────────
function sparklinePath(scores: number[], w = 44, h = 14): string {
  if (!scores || scores.length < 2) return ''
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const range = max - min || 1
  const pts = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * w
    const y = h - ((s - min) / range) * (h - 2) - 1
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return `M ${pts.join(' L ')}`
}

function handleExportDocx() {
  if (!selectedUpload.value) return
  try {
    exportDocx(selectedUpload.value.upload_id)
    exportFeedback.value = 'Download started — check your browser downloads.'
    setTimeout(() => { exportFeedback.value = null }, 4000)
  } catch {
    exportFeedback.value = 'Export failed — please try again.'
  }
}

function handleResponseToReviewers() {
  if (!selectedUpload.value) return
  try {
    getResponseToReviewers(selectedUpload.value.upload_id, 'docx')
    exportFeedback.value = 'Response document opened in new tab.'
    setTimeout(() => { exportFeedback.value = null }, 4000)
  } catch {
    exportFeedback.value = 'Export failed — please try again.'
  }
}

function handleRewriteInstructions() {
  if (!selectedUpload.value) return
  getRewriteInstructions(selectedUpload.value.upload_id)
  exportFeedback.value = 'Rewrite instructions opened in new tab.'
}

const isPaperLabEmpty = computed(() => uploads.value.length === 0 && !loadingUploads.value)

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="paper-lab">
    <div v-if="isPaperLabEmpty" class="paper-lab__hero">
      <h1 class="paper-lab__title" style="text-align: center; margin-bottom: 8px;">Paper Lab</h1>
      <p class="paper-lab__subtitle" style="text-align: center; margin-bottom: 32px;">Upload manuscripts for AI-driven adversarial review and rehabilitation</p>
<!-- ── Upload Zone ── -->
    <GlassPanel
      elevated
      padding="0"
      class="upload-zone"
      :class="{ 'upload-zone--active': dragOver, 'upload-zone--uploading': uploading }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="upload-zone__inner">
        <span class="material-symbols-outlined upload-zone__icon">
          {{ uploading ? 'progress_activity' : 'cloud_upload' }}
        </span>
        <p class="upload-zone__text">
          {{ uploading ? 'Uploading...' : 'Drop a .pdf, .doc, .docx, .txt, .md, or .markdown file here' }}
        </p>
        <label v-if="!uploading" class="upload-zone__browse">
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt,.md,.markdown"
            class="sr-only"
            @change="handleFileSelect"
          />
          <ActionButton variant="secondary" size="sm" icon="folder_open">
            Browse Files
          </ActionButton>
        </label>
      </div>
    </GlassPanel>
    </div>

    <div v-else class="paper-lab__layout">
      <!-- ── Left: Previous Uploads ── -->
      <div class="paper-lab__sidebar">
        <h1 class="paper-lab__title" style="font-size: 20px; margin-bottom: 4px;">Paper Lab</h1>
        <p class="paper-lab__subtitle" style="font-size: 11px; margin-bottom: 16px;">Adversarial review & rehab</p>
<!-- ── Upload Zone ── -->
    <GlassPanel
      elevated
      padding="0"
      class="upload-zone upload-zone--compact"
      :class="{ 'upload-zone--active': dragOver, 'upload-zone--uploading': uploading }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="upload-zone__inner">
        <span class="material-symbols-outlined upload-zone__icon">
          {{ uploading ? 'progress_activity' : 'cloud_upload' }}
        </span>
        <p class="upload-zone__text">
          {{ uploading ? 'Uploading...' : 'Drop a .pdf, .doc, .docx, .txt, .md, or .markdown file here' }}
        </p>
        <label v-if="!uploading" class="upload-zone__browse">
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt,.md,.markdown"
            class="sr-only"
            @change="handleFileSelect"
          />
          <ActionButton variant="secondary" size="sm" icon="folder_open">
            Browse Files
          </ActionButton>
        </label>
      </div>
    </GlassPanel>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; margin-top: 4px;">
          <h3 class="sidebar-title" style="margin: 0">Uploads</h3>
          <label style="font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px; color: var(--text-secondary); background: rgba(255,255,255,0.05); padding: 4px 8px; border-radius: 4px;">
            <input type="checkbox" v-model="compareMode" style="accent-color: #ccff00;" />
            Compare Mode
          </label>
        </div>

        <div v-if="loadingUploads" class="loading-row">
          <span class="material-symbols-outlined spin">progress_activity</span>
        </div>

        <div v-else-if="uploadsError" class="error-hint">
          <span class="material-symbols-outlined" style="font-size: 18px; color: var(--error)">cloud_off</span>
          <span>{{ uploadsError }}</span>
          <button class="retry-link" @click="fetchUploads">Retry</button>
        </div>

        <div v-else-if="uploads.length === 0" class="empty-hint">
          No uploads yet
        </div>

        <div
          v-for="upload in uploads"
          :key="upload.upload_id"
          class="upload-item"
          :class="{ 
            'upload-item--selected': !compareMode && selectedUpload?.upload_id === upload.upload_id,
            'upload-item--compare': compareMode,
            'upload-item--compare-selected': compareMode && selectedUploadIds.includes(upload.upload_id)
          }"
          @click="compareMode ? toggleCompare(upload.upload_id) : selectUpload(upload)"
        >
          <div class="upload-item__top">
            <input v-if="compareMode" type="checkbox" :checked="selectedUploadIds.includes(upload.upload_id)" style="margin-right: 8px; pointer-events: none; accent-color: #ccff00;" />
            <span class="upload-item__title">{{ upload.title || 'Untitled' }}</span>
            <StatusBadge
              :status="uploadBadgeStatus(upload.status)"
              size="sm"
            />
          </div>
          <div class="upload-item__meta">
            <span>{{ upload.language }} / {{ upload.field }}</span>
            <span>{{ formatDate(upload.created_at) }}</span>
          </div>
          <div class="upload-item__parse">
            <span class="upload-item__parser">{{ parserLabel(upload.parser_engine) }}</span>
            <span class="upload-item__parse-pill" :class="`upload-item__parse-pill--${parseQualityClass(upload)}`">
              {{ parseQualityLabel(upload) }}
            </span>
            <span v-if="upload.ocr_used" class="upload-item__ocr">OCR</span>
          </div>
          <!-- Sparkline + round count -->
          <div class="upload-item__bottom">
            <div v-if="upload.review_scores && upload.review_scores.length > 1" class="upload-item__sparkline">
              <svg width="44" height="14" style="overflow: visible">
                <path
                  :d="sparklinePath(upload.review_scores)"
                  fill="none"
                  :stroke="scoreColorHex(upload.review_scores[upload.review_scores.length - 1] ?? 5)"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </div>
            <div v-else-if="upload.review_scores && upload.review_scores.length === 1" class="upload-item__scores">
              <span
                class="score-dot"
                :style="{ background: scoreColor(upload.review_scores[0] ?? 5) }"
                :title="`Score: ${(upload.review_scores[0] ?? 0).toFixed(1)}`"
              />
            </div>
            <span v-if="(upload.round_count ?? 0) > 0" class="upload-item__rounds font-mono">
              {{ upload.round_count }} rnd
            </span>
          </div>
        </div>
      </div>
      <!-- ── Right: Detail Panel ── -->
      <div class="paper-lab__main" style="display: flex; flex-direction: column; gap: 16px; width: 100%; height: 100%;">
        <template v-if="compareMode">
          <ComparativeAnalysisPanel :uploads="selectedUploadsFull" />
        </template>
        <template v-else-if="selectedUpload">
          <!-- Header: Breadcrumb + Actions -->
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <StatusBreadcrumb :status="selectedUpload.status" />
            <div style="display: flex; gap: 8px; flex-shrink: 0;">
              <ActionButton v-if="isReadyForReview(selectedUpload.status)" variant="primary" icon="play_arrow" @click="handleStartReview" :loading="reviewing">Start Adversarial Review</ActionButton>
              <template v-else-if="isReviewComplete(selectedUpload.status)">
                <ActionButton variant="secondary" icon="download" @click="handleExportDocx">Docx</ActionButton>
                <ActionButton variant="secondary" icon="comment" @click="handleResponseToReviewers">Reviews</ActionButton>
                <ActionButton variant="secondary" icon="edit" @click="handleRewriteInstructions">Rewrite</ActionButton>
                <ActionButton variant="secondary" icon="psychology" @click="handleSpecialistReview" :loading="runningSpecialist">Specialist</ActionButton>
              </template>
            </div>
          </div>

          <!-- Export feedback (Bug #10) -->
          <div v-if="exportFeedback" class="export-feedback">
            <span class="material-symbols-outlined" style="font-size: 16px;">info</span>
            <span>{{ exportFeedback }}</span>
          </div>

          <div v-if="inlineNotice" class="export-feedback export-feedback--neutral">
            <span class="material-symbols-outlined" style="font-size: 16px;">tips_and_updates</span>
            <span>{{ inlineNotice }}</span>
          </div>

          <!-- Paper Info Card -->
          <GlassPanel class="paper-info" padding="16px">
            <div class="paper-info__header">
              <h2 class="paper-info__title">{{ selectedUpload.title || 'Untitled Manuscript' }}</h2>
              <StatusBadge :status="uploadBadgeStatus(selectedUpload.status)" />
            </div>
            <div class="paper-info__meta">
              <span><strong>Field:</strong> {{ selectedUpload.field || selectedUpload.detected_field || 'Undetected' }}</span>
              <span><strong>Language:</strong> {{ selectedUpload.language || 'en' }}</span>
              <span><strong>Uploaded:</strong> {{ formatDate(selectedUpload.created_at) }}</span>
              <span><strong>Parser:</strong> {{ parserLabel(selectedUpload.parser_engine) }}</span>
              <span><strong>Parse Quality:</strong> {{ parseQualityLabel(selectedUpload) }}</span>
              <span v-if="(selectedUpload.round_count ?? 0) > 0"><strong>Rounds:</strong> {{ selectedUpload.round_count }}</span>
              <span v-if="selectedUpload.initial_score != null"><strong>Initial Score:</strong> {{ selectedUpload.initial_score?.toFixed(1) }}</span>
              <span v-if="selectedUpload.final_score != null"><strong>Final Score:</strong> {{ selectedUpload.final_score?.toFixed(1) }}</span>
            </div>
            <div class="paper-info__parse-grid">
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">Overall</span>
                <strong>{{ parseOverallScore(selectedUpload) != null ? parseOverallScore(selectedUpload)?.toFixed(2) : 'n/a' }}</strong>
              </div>
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">Sections</span>
                <strong>{{ selectedUpload.document_counts?.sections ?? 0 }}</strong>
              </div>
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">Tables</span>
                <strong>{{ selectedUpload.document_counts?.tables ?? 0 }}</strong>
              </div>
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">Figures</span>
                <strong>{{ selectedUpload.document_counts?.figures ?? 0 }}</strong>
              </div>
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">Formulas</span>
                <strong>{{ selectedUpload.document_counts?.formulas ?? 0 }}</strong>
              </div>
              <div class="paper-info__parse-card">
                <span class="paper-info__parse-label">References</span>
                <strong>{{ selectedUpload.document_counts?.references ?? 0 }}</strong>
              </div>
            </div>
            <div class="paper-info__drilldown">
              <div class="paper-info__drilldown-header">
                <h3 class="paper-info__drilldown-title">Document Parse</h3>
                <span v-if="loadingUploadDetail" class="paper-info__loading">Refreshing…</span>
              </div>
              <div class="paper-info__quality-list">
                <div class="paper-info__quality-item">
                  <span>Title detection</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.title_confidence) }}</strong>
                </div>
                <div class="paper-info__quality-item">
                  <span>Section coverage</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.section_coverage) }}</strong>
                </div>
                <div class="paper-info__quality-item">
                  <span>Reading order</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.reading_order) }}</strong>
                </div>
                <div class="paper-info__quality-item">
                  <span>Table retention</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.table_retention) }}</strong>
                </div>
                <div class="paper-info__quality-item">
                  <span>Figure retention</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.figure_retention) }}</strong>
                </div>
                <div class="paper-info__quality-item">
                  <span>Formula retention</span>
                  <strong>{{ formatParseMetric(selectedUpload.parse_quality_breakdown?.formula_retention) }}</strong>
                </div>
              </div>
              <div v-if="selectedUpload.parse_warnings?.length" class="paper-info__warnings">
                <div class="paper-info__warnings-title">Parse warnings</div>
                <ul class="paper-info__warning-list">
                  <li v-for="(warning, index) in selectedUpload.parse_warnings" :key="index">{{ warning }}</li>
                </ul>
              </div>
              <div class="paper-info__entity-grid">
                <div class="paper-info__entity-card">
                  <div class="paper-info__entity-title">Sections</div>
                  <div class="paper-info__entity-values">
                    <span v-for="section in selectedUpload.sections?.slice(0, 6)" :key="section">{{ section }}</span>
                    <span v-if="!selectedUpload.sections?.length">None</span>
                  </div>
                </div>
                <div class="paper-info__entity-card">
                  <div class="paper-info__entity-title">Tables</div>
                  <div class="paper-info__entity-previews">
                    <div v-for="(table, index) in selectedUpload.tables?.slice(0, 3)" :key="index" class="paper-info__entity-preview">
                      <div class="paper-info__entity-preview-header">
                        <strong>{{ String(table.ref ?? table.table_id ?? table.title ?? `Table ${index + 1}`) }}</strong>
                        <div class="paper-info__entity-preview-meta">
                          <span>{{ pageLabel(table) }}</span>
                          <span v-if="bboxLabel(table)">{{ bboxLabel(table) }}</span>
                        </div>
                      </div>
                      <p>{{ tablePreview(table) }}</p>
                    </div>
                    <span v-if="!selectedUpload.tables?.length">None</span>
                  </div>
                </div>
                <div class="paper-info__entity-card">
                  <div class="paper-info__entity-title">Figures</div>
                  <div class="paper-info__entity-previews">
                    <div v-for="(figure, index) in selectedUpload.figures?.slice(0, 3)" :key="index" class="paper-info__entity-preview">
                      <div class="paper-info__entity-preview-header">
                        <strong>{{ String(figure.ref ?? figure.figure_id ?? figure.title ?? `Figure ${index + 1}`) }}</strong>
                        <div class="paper-info__entity-preview-meta">
                          <span>{{ pageLabel(figure) }}</span>
                          <span v-if="bboxLabel(figure)">{{ bboxLabel(figure) }}</span>
                        </div>
                      </div>
                      <p>{{ figurePreview(figure) }}</p>
                    </div>
                    <span v-if="!selectedUpload.figures?.length">None</span>
                  </div>
                </div>
                <div class="paper-info__entity-card">
                  <div class="paper-info__entity-title">Formulas</div>
                  <div class="paper-info__entity-previews">
                    <div v-for="(formula, index) in selectedUpload.formulas?.slice(0, 3)" :key="index" class="paper-info__entity-preview">
                      <div class="paper-info__entity-preview-header">
                        <strong>{{ String(formula.ref ?? formula.formula_id ?? `Formula ${index + 1}`) }}</strong>
                        <div class="paper-info__entity-preview-meta">
                          <span>{{ pageLabel(formula) }}</span>
                          <span v-if="bboxLabel(formula)">{{ bboxLabel(formula) }}</span>
                        </div>
                      </div>
                      <p class="paper-info__formula-preview">{{ formulaPreview(formula) }}</p>
                    </div>
                    <span v-if="!selectedUpload.formulas?.length">None</span>
                  </div>
                </div>
              </div>
            </div>
          </GlassPanel>

          <!-- Review Progress -->
          <div v-if="reviewing || reviewProgress" class="review-progress">
            <span class="material-symbols-outlined spin" style="font-size: 18px; color: var(--os-brand);">progress_activity</span>
            <span>{{ reviewProgress || 'Processing...' }}</span>
          </div>

          <!-- Review Config (for ready-to-review uploads) -->
          <GlassPanel v-if="isReadyForReview(selectedUpload.status) && !reviewing" class="review-config" padding="16px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h3 style="margin: 0; font-size: 14px; color: var(--text-primary);">Review Configuration</h3>
              <button class="config-toggle" @click="showConfig = !showConfig">
                <span class="material-symbols-outlined" style="font-size: 16px;">{{ showConfig ? 'expand_less' : 'expand_more' }}</span>
                {{ showConfig ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div v-if="showConfig" class="config-grid">
              <label class="config-item">
                <span>Rounds</span>
                <input type="number" v-model.number="reviewConfig.rounds" min="1" max="10" class="config-input" />
              </label>
              <label class="config-item">
                <span>Reviewers</span>
                <input type="number" v-model.number="reviewConfig.reviewers" min="2" max="10" class="config-input" />
              </label>
              <label class="config-item">
                <span>Authors</span>
                <input type="number" v-model.number="reviewConfig.authors" min="1" max="5" class="config-input" />
              </label>
              <label class="config-item" style="flex-direction: row; gap: 8px;">
                <input type="checkbox" v-model="reviewConfig.live" style="accent-color: var(--os-brand);" />
                <span>Live streaming</span>
              </label>
            </div>
            <p v-else class="config-summary">{{ reviewConfig.rounds }} rounds · {{ reviewConfig.reviewers }} reviewers · {{ reviewConfig.authors }} authors</p>
          </GlassPanel>

          <ReviewOverviewPanel
            v-if="isReviewComplete(selectedUpload.status)"
            :title="selectedUpload.title || 'Untitled Manuscript'"
            :roundsData="roundsData"
            :currentDraft="currentDraft"
            :specialistResults="specialistResults"
            :specialistStatus="specialistStatus"
          />

          <VisualizationStudio
            v-if="isReviewComplete(selectedUpload.status)"
            :uploadId="selectedUpload.upload_id"
          />

          <!-- Awaiting Review placeholder -->
          <div v-if="isReadyForReview(selectedUpload.status) && !reviewing" class="awaiting-review">
            <span class="material-symbols-outlined" style="font-size: 40px; color: var(--text-tertiary); margin-bottom: 12px;">science</span>
            <p style="color: var(--text-secondary); font-size: 14px; margin: 0;">Ready for adversarial review. Click <strong>Start Adversarial Review</strong> above to begin the multi-round peer review simulation.</p>
          </div>
        </template>
        <!-- Bug #9: importing state -->
        <div v-else-if="importing" class="empty-main">
          <span class="material-symbols-outlined" style="font-size: 48px; color: var(--os-brand); margin-bottom: 16px; animation: spin 1.2s linear infinite;">sync</span>
          <p class="empty-main__hint">Importing pipeline draft...</p>
        </div>
        <div v-else-if="importError" class="empty-main">
          <span class="material-symbols-outlined" style="font-size: 48px; color: #dc2626; margin-bottom: 16px;">error_outline</span>
          <p class="empty-main__hint" style="color: #dc2626;">{{ importError }}</p>
        </div>
        <div v-else class="empty-main">
          <span class="material-symbols-outlined" style="font-size: 48px; color: var(--text-tertiary); margin-bottom: 16px;">query_stats</span>
          <p class="empty-main__hint">Select an upload or drag a new manuscript to begin.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.paper-lab {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.paper-lab__title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
}

.paper-lab__subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin: -12px 0 0;
}

.paper-lab__hero {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
  padding: 40px;
}

.paper-lab__hero .upload-zone {
  width: 100%;
  max-width: 600px;
}

.upload-zone {
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.upload-zone--active {
  border-color: var(--os-brand);
  background: var(--bg-active);
}

.upload-zone--uploading {
  pointer-events: none;
}

.upload-zone__inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 24px;
}

.upload-zone__icon {
  font-size: 36px;
  color: var(--os-brand);
}

.upload-zone--uploading .upload-zone__icon {
  animation: btn-spin 1s linear infinite;
}

.upload-zone__text {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.upload-zone--compact .upload-zone__inner {
  padding: 16px;
  gap: 8px;
}

.upload-zone--compact .upload-zone__icon {
  font-size: 24px;
}

.upload-zone--compact .upload-zone__text {
  font-size: 12px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.paper-lab__layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  min-height: calc(100vh - 120px);
  align-items: start;
}

.paper-lab__sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 4px;
}

.upload-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.upload-item:hover {
  border-color: var(--border-primary);
}

.upload-item--selected {
  border-color: var(--os-brand);
  background: var(--bg-active);
}

.upload-item--compare-selected {
  border-color: #ccff00;
}

.upload-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.upload-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-item__meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-tertiary);
}

.upload-item__parse {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 10px;
  color: var(--text-tertiary);
}

.upload-item__parser {
  color: var(--text-secondary);
}

.upload-item__parse-pill,
.upload-item__ocr {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 999px;
  border: 1px solid var(--border-secondary);
  background: rgba(255, 255, 255, 0.04);
}

.upload-item__parse-pill--good {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.35);
}

.upload-item__parse-pill--warn {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.35);
}

.upload-item__parse-pill--bad {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.35);
}

.upload-item__bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-item__scores {
  display: flex;
  gap: 4px;
}

.score-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.empty-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-secondary);
  min-height: 400px;
  border: 1px dashed var(--border-secondary);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.02);
}

.empty-main__hint {
  font-size: 14px;
  color: var(--text-secondary);
}

@keyframes btn-spin {
  100% { transform: rotate(360deg); }
}

/* Paper Info Card */
.paper-info__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.paper-info__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-info__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.paper-info__meta strong {
  color: var(--text-primary);
}

.paper-info__parse-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.paper-info__parse-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  background: rgba(255, 255, 255, 0.03);
}

.paper-info__parse-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.paper-info__drilldown {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.paper-info__drilldown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.paper-info__drilldown-title {
  margin: 0;
  font-size: 13px;
  color: var(--text-primary);
}

.paper-info__loading {
  font-size: 11px;
  color: var(--text-tertiary);
}

.paper-info__quality-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.paper-info__quality-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-secondary);
  font-size: 12px;
  color: var(--text-secondary);
}

.paper-info__warnings {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paper-info__warnings-title,
.paper-info__entity-title {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.paper-info__warning-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
}

.paper-info__entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.paper-info__entity-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-secondary);
}

.paper-info__entity-values {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.paper-info__entity-values span {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-secondary);
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 100%;
}

.paper-info__entity-previews {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paper-info__entity-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-secondary);
}

.paper-info__entity-preview strong {
  font-size: 12px;
  color: var(--text-primary);
}

.paper-info__entity-preview-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.paper-info__entity-preview-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.paper-info__entity-preview-header span {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.paper-info__entity-preview p {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.45;
}

.paper-info__formula-preview {
  font-family: var(--font-mono);
  word-break: break-word;
}

.export-feedback--neutral {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

/* Review Progress */
.review-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(204, 255, 0, 0.06);
  border: 1px solid var(--os-brand-subtle, rgba(204, 255, 0, 0.2));
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
}

.spin {
  animation: btn-spin 1s linear infinite;
}

/* Review Config */
.config-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 8px;
  border-radius: 4px;
  transition: background var(--transition-fast);
}

.config-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.config-input {
  padding: 6px 10px;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 13px;
  width: 100%;
  transition: border-color var(--transition-fast);
}

.config-input:focus {
  outline: none;
  border-color: var(--os-brand);
}

.config-summary {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

/* Awaiting Review */
.awaiting-review {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 200px;
  border: 1px dashed var(--border-secondary);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.02);
  padding: 32px;
}

/* Review Overview */
.review-overview__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.review-overview__title,
.current-draft__title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}
.review-overview__score {
  font-size: 14px;
  color: var(--text-secondary);
}
.review-overview__empty {
  color: var(--text-tertiary);
  font-style: italic;
  margin: 0;
}
.review-rounds {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.review-round-card {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  background: var(--bg-tertiary);
}
.review-round-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.review-round-card__comments {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.review-comment {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}
.review-comment__severity {
  flex-shrink: 0;
  text-transform: uppercase;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.04em;
  padding: 1px 6px;
  border-radius: 4px;
  align-self: flex-start;
}
.review-comment__severity--critical { background: #fecaca; color: #991b1b; }
.review-comment__severity--major    { background: #fde68a; color: #92400e; }
.review-comment__severity--minor    { background: #bfdbfe; color: #1e40af; }
.review-comment__severity--suggestion { background: #e5e7eb; color: #374151; }
.review-comment--more { font-size: 12px; color: var(--text-tertiary); font-style: italic; }

/* Current draft section */
.current-draft__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.current-draft__words {
  font-size: 12px;
  color: var(--text-tertiary);
}
.current-draft__toc {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
}
.current-draft__toc-label {
  color: var(--text-tertiary);
}
.current-draft__toc-item {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  padding: 2px 8px;
  color: var(--text-secondary);
}

/* Export feedback */
.export-feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  animation: fadeIn 200ms ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Responsive */
@media (max-width: 768px) {
  .paper-lab__body {
    flex-direction: column !important;
  }
  .paper-lab__body > * {
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }
}
</style>
