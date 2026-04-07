import { computed } from 'vue'
import { usePipelineStore } from '@/stores/pipeline'
import type { NextStepRecommendation, StageId, StageInfo } from '@/types/pipeline'
import { STAGE_ORDER, STAGE_LABELS, STAGE_DESCRIPTIONS } from '@/types/pipeline'
import { getPathRecommendation } from '@/api/ais'

/**
 * Recommendation engine composable.
 *
 * Inspects the current pipeline stages and returns a computed recommendation
 * for the next logical action the researcher should take.
 *
 * Logic priority:
 *   1. Find the first stage that is pending or failed (follow STAGE_ORDER).
 *   2. If a draft exists with review_overall < 4, recommend paper rehab.
 *   3. After ideas stage, check backend path recommendation.
 */
export function useNextStep() {
  const pipeline = usePipelineStore()

  const recommendation = computed<NextStepRecommendation | null>(() => {
    const stageMap = pipeline.stages
    if (!stageMap || Object.keys(stageMap).length === 0) return null

    // -- Check for draft quality issue first (high priority) --
    const draftResult = pipeline.stageResults['draft']
    if (
      draftResult &&
      typeof draftResult === 'object' &&
      'review_overall' in draftResult &&
      typeof draftResult.review_overall === 'number' &&
      draftResult.review_overall < 4
    ) {
      return {
        action: 'rehab',
        label: 'Improve Paper Draft',
        description: `Draft scored ${draftResult.review_overall}/10. Paper rehabilitation can improve structure, arguments, and citations.`,
        route: '/paper-lab',
        urgent: true,
        actions: [
          { label: 'Start Rehab', primary: true, handler: 'startRehab' },
          { label: 'View Draft', handler: 'viewDraft' },
        ],
      }
    }

    // -- Walk stage order, find first incomplete stage --
    for (const stageId of STAGE_ORDER) {
      const stage: StageInfo | undefined = stageMap[stageId]
      if (!stage) continue

      if (stage.status === 'failed') {
        return {
          action: stageId,
          label: `Retry ${STAGE_LABELS[stageId]}`,
          description: `The ${STAGE_LABELS[stageId].toLowerCase()} stage failed. Retry to continue the pipeline.`,
          route: `/pipeline/${stageId}`,
          urgent: true,
          actions: [
            { label: 'Retry', primary: true, handler: `retry_${stageId}` },
            { label: 'Skip', handler: `skip_${stageId}` },
          ],
        }
      }

      if (stage.status === 'pending') {
        return buildPendingRecommendation(stageId, stageMap)
      }
    }

    // -- All stages done --
    return {
      action: 'complete',
      label: 'Pipeline Complete',
      description: 'All stages have finished. Review results or start a new project.',
      actions: [
        { label: 'View Results', primary: true, handler: 'viewResults' },
        { label: 'New Project', handler: 'newProject' },
      ],
    }
  })

  /**
   * Fetch an async path recommendation from the backend after ideas stage.
   * Returns a promise so callers can await; the computed `recommendation`
   * above handles the synchronous fallback.
   */
  async function fetchPathRecommendation(runId: string): Promise<NextStepRecommendation | null> {
    try {
      const res = await getPathRecommendation(runId)
      if (res.data.success && res.data.data) {
        return res.data.data as unknown as NextStepRecommendation
      }
    } catch {
      // Fall back to computed recommendation
    }
    return null
  }

  return {
    recommendation,
    fetchPathRecommendation,
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildPendingRecommendation(
  stageId: StageId,
  stageMap: Record<StageId, StageInfo>,
): NextStepRecommendation {
  // If the stage is marked done or active, skip to the next pending stage
  const stage = stageMap[stageId]
  if (stage && (stage.status === 'done' || stage.status === 'active')) {
    // Find the actual next pending stage
    const idx = STAGE_ORDER.indexOf(stageId)
    for (let i = idx + 1; i < STAGE_ORDER.length; i++) {
      const nextId: StageId | undefined = STAGE_ORDER[i]
      if (!nextId) continue
      const next = stageMap[nextId]
      if (next && next.status === 'pending') {
        return buildPendingRecommendation(nextId, stageMap)
      }
    }
    // All remaining stages are done/active — pipeline complete
    return {
      action: 'complete',
      label: 'Pipeline Complete',
      description: 'All stages have finished. Review results or start a new project.',
      actions: [
        { label: 'View Results', primary: true, handler: 'viewResults' },
        { label: 'New Project', handler: 'newProject' },
      ],
    }
  }

  const label = STAGE_LABELS[stageId]

  return {
    action: stageId,
    label: `Run ${label}`,
    description: STAGE_DESCRIPTIONS[stageId],
    route: `/pipeline/${stageId}`,
    cost: stageId === 'experiment' ? 'High (GPU required)' : undefined,
    actions: [
      { label: `Start ${label}`, primary: true, handler: `start_${stageId}` },
      { label: 'Auto-Advance All', handler: 'autoAdvance' },
    ],
  }
}
