<script setup lang="ts">
import { ref } from 'vue'
import {
  generatePaperBananaIllustration,
  type PaperBananaResult,
} from '@/api/paperLab'

const props = defineProps<{
  uploadId: string
}>()

const isLoading = ref(false)
const taskType = ref<'diagram' | 'plot'>('diagram')
const visualIntent = ref('')
const result = ref<PaperBananaResult | null>(null)
const errorMsg = ref('')

async function runIllustration() {
  if (!visualIntent.value.trim()) {
    errorMsg.value = 'Please provide a description of the intended visual.'
    return
  }

  isLoading.value = true
  errorMsg.value = ''
  result.value = null

  try {
    const res = await generatePaperBananaIllustration(props.uploadId, visualIntent.value, taskType.value)
    if (res.data.success && res.data.data) {
      result.value = res.data.data
    } else {
      errorMsg.value = res.data.error || 'Failed to generate illustration'
    }
  } catch (err: any) {
    errorMsg.value = err.response?.data?.error || err.message || 'An error occurred'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="paper-banana-panel space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <h3 class="text-xl font-semibold text-white tracking-wide">
          <i class="ri-palette-line mr-2 text-primary-500"></i>
          PaperBanana Agentic Illustrator
        </h3>
        <p class="text-sm text-gray-400 mt-1">
          Orchestrated multi-agent pipeline generating publication-ready methodology diagrams and plots using Gemini 2.0.
        </p>
      </div>
    </div>

    <!-- Request Form -->
    <div class="bg-dark-900 border border-gray-800 rounded-xl p-6">
      <h4 class="text-sm uppercase tracking-wider text-gray-500 mb-4 font-semibold">New Generation Request</h4>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-400 mb-1">Task Type</label>
          <div class="flex space-x-4">
            <label class="inline-flex items-center cursor-pointer">
              <input type="radio" class="form-radio text-primary-500 bg-dark-800 border-gray-700" value="diagram" v-model="taskType" />
              <span class="ml-2 text-gray-300">Methodology Diagram</span>
            </label>
            <label class="inline-flex items-center cursor-pointer">
              <input type="radio" class="form-radio text-emerald-500 bg-dark-800 border-gray-700" value="plot" v-model="taskType" />
              <span class="ml-2 text-gray-300">Statistical Plot</span>
            </label>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-400 mb-1">Visual Intent / Caption</label>
          <textarea
            v-model="visualIntent"
            class="w-full bg-dark-950 border border-gray-800 rounded-lg p-3 text-sm text-gray-300 placeholder-gray-600 focus:ring-1 focus:ring-primary-500 outline-none transition-shadow min-h-[100px]"
            placeholder="e.g. A flowchart explaining the reinforcement learning pipeline from data ingestion to model deployment..."
          ></textarea>
        </div>

        <div class="flex justify-end">
          <button
            @click="runIllustration"
            :disabled="isLoading || !visualIntent.trim()"
            class="px-6 py-2 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors flex items-center"
          >
            <i class="ri-magic-line mr-2" :class="{ 'animate-spin ri-loader-4-line': isLoading }"></i>
            {{ isLoading ? 'Agentic Pipeline Active...' : 'Generate Illustration' }}
          </button>
        </div>
        
        <div v-if="errorMsg" class="mt-4 p-4 bg-red-900/20 border border-red-500/20 rounded-lg text-red-400 text-sm">
          <i class="ri-error-warning-line mr-2"></i> {{ errorMsg }}
        </div>
      </div>
    </div>

    <!-- Results Section -->
    <div v-if="result" class="space-y-6">
      
      <!-- Intermediate Generation Steps -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Planner -->
        <div class="bg-dark-900 border border-gray-800 rounded-xl p-5 shadow-inner">
          <h4 class="text-sm font-semibold text-gray-400 mb-3 flex items-center">
            <i class="ri-brain-line mr-2 text-blue-400"></i> Planner Agent Output
          </h4>
          <div class="text-xs text-gray-300 bg-dark-950 p-4 rounded-lg overflow-y-auto max-h-48 border border-gray-800">
            {{ result.planner_output }}
          </div>
        </div>
        
        <!-- Stylist -->
        <div class="bg-dark-900 border border-gray-800 rounded-xl p-5 shadow-inner">
          <h4 class="text-sm font-semibold text-gray-400 mb-3 flex items-center">
            <i class="ri-quill-pen-line mr-2 text-purple-400"></i> Stylist Agent Output
          </h4>
          <div class="text-xs text-gray-300 bg-dark-950 p-4 rounded-lg overflow-y-auto max-h-48 border border-gray-800">
            {{ result.stylist_output }}
          </div>
        </div>
      </div>

      <!-- Final Viz Output -->
      <div class="bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-lg p-5">
        <h4 class="text-lg font-semibold text-white mb-4 flex items-center">
          <i class="ri-image-edit-line mr-2 text-primary-400"></i> Final Rendering
        </h4>

        <div v-if="result.format === 'mermaid'" class="p-6 bg-dark-950 rounded-lg overflow-x-auto border border-gray-800 flex justify-center">
          <!-- We normally compile mermaid dynamically, here we output the raw block ready for our Mermaid component -->
          <pre class="text-xs text-primary-300 whitespace-pre-wrap">{{ result.visualizer_output }}</pre>
        </div>

        <div v-else-if="result.format === 'base64_jpg'" class="p-6 bg-dark-950 rounded-lg flex justify-center border border-gray-800 relative">
          <img :src="'data:image/jpeg;base64,' + result.visualizer_output" class="max-w-full h-auto rounded shadow-lg" alt="Generated Statistical Plot" />
        </div>
        
        <div v-else class="p-6 bg-dark-950 rounded-lg text-center text-red-500 text-sm">
          <i class="ri-error-warning-line text-2xl mb-2 block"></i>
          Failed to compile executable output layer. Check Python logs or Mermaid syntax.
        </div>
        
        <!-- Generated Code -->
        <div v-if="result.code" class="mt-4">
           <details class="bg-dark-950 border border-gray-800 rounded-lg">
             <summary class="cursor-pointer px-4 py-3 text-sm font-medium text-gray-400 hover:text-white transition-colors flex items-center">
               <i class="ri-code-s-slash-line mr-2"></i> View Generated Python Code
             </summary>
             <div class="px-4 pb-4">
               <pre class="text-xs text-gray-400 overflow-x-auto bg-[#0a0a0a] p-3 rounded">{{ result.code }}</pre>
             </div>
           </details>
        </div>
      </div>
      
    </div>
  </div>
</template>
