<script setup lang="ts">
defineProps<{
  original: string
  improved: string
  rationale: string
  sectionHint?: string
}>()
</script>

<template>
  <div class="statement-diff">
    <!-- Section badge -->
    <div v-if="sectionHint" class="sd-section-badge">
      <span class="material-symbols-outlined" style="font-size: 12px">article</span>
      {{ sectionHint }}
    </div>

    <!-- Two-column diff -->
    <div class="sd-columns">
      <!-- Original -->
      <div class="sd-col sd-col--before">
        <div class="sd-col__label">
          <span class="material-symbols-outlined" style="font-size: 13px">cancel</span>
          Original
        </div>
        <blockquote class="sd-quote sd-quote--before">
          "{{ original }}"
        </blockquote>
      </div>

      <!-- Arrow -->
      <div class="sd-arrow">
        <span class="material-symbols-outlined">arrow_forward</span>
      </div>

      <!-- Improved -->
      <div class="sd-col sd-col--after">
        <div class="sd-col__label">
          <span class="material-symbols-outlined" style="font-size: 13px">check_circle</span>
          Improved
        </div>
        <blockquote class="sd-quote sd-quote--after">
          "{{ improved }}"
        </blockquote>
      </div>
    </div>

    <!-- Rationale -->
    <div class="sd-rationale">
      <span class="material-symbols-outlined" style="font-size: 13px; color: var(--os-brand)">lightbulb</span>
      <span>{{ rationale }}</span>
    </div>
  </div>
</template>

<style scoped>
.statement-diff {
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-primary);
}

.sd-section-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 10px 12px 0;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--os-brand);
  background: var(--os-brand-light);
  padding: 2px 7px;
  border-radius: var(--radius-pill);
}

/* Two-column diff */
.sd-columns {
  display: grid;
  grid-template-columns: 1fr 28px 1fr;
  align-items: start;
  gap: 0;
  padding: 10px 12px;
}

.sd-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sd-col__label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.sd-col--before .sd-col__label { color: var(--error); }
.sd-col--after  .sd-col__label { color: var(--success); }

.sd-quote {
  font-size: 12px;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  margin: 0;
  font-style: italic;
}

.sd-quote--before {
  color: var(--error);
  background: rgba(239, 68, 68, 0.06);
  border-left: 3px solid var(--error);
}

.sd-quote--after {
  color: var(--success);
  background: rgba(34, 197, 94, 0.06);
  border-left: 3px solid var(--success);
}

.sd-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 24px;
  color: var(--text-tertiary);
}

.sd-arrow .material-symbols-outlined {
  font-size: 18px;
}

/* Rationale */
.sd-rationale {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 12px 10px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-secondary);
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>
