<script setup>
import { ref } from 'vue'
import { useTranscriptionStore } from '../stores/transcription'

const store = useTranscriptionStore()
const fileInput = ref(null)

const languages = [
  { code: 'auto', name: '자동 감지' },
  { code: 'ko', name: '한국어' },
  { code: 'en', name: '영어' },
  { code: 'ja', name: '일본어' },
  { code: 'zh', name: '중국어' },
  { code: 'es', name: '스페인어' },
  { code: 'fr', name: '프랑스어' },
]

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) store.setFile(file)
}
const handleDragOver = (event) => event.preventDefault()
const handleDrop = (event) => {
  event.preventDefault()
  const file = event.dataTransfer.files[0]
  if (file) store.setFile(file)
}
const triggerFileInput = () => fileInput.value.click()
const startTranscription = () => store.startTranscription()
const advancedOpen = ref(false)
</script>

<template>
  <div class="bg-white rounded-2xl shadow-xl p-8">
    <div @dragover="handleDragOver" @drop="handleDrop" @click="triggerFileInput" class="border-3 border-dashed border-gray-300 rounded-xl p-12 text-center cursor-pointer hover:border-indigo-400 hover:bg-indigo-50 transition-all duration-300">
      <div class="text-6xl mb-4">📹</div>
      <p class="text-lg font-medium text-gray-700 mb-2">동영상 파일을 드래그하거나 클릭하세요</p>
      <p class="text-sm text-gray-500">MP4, AVI, MOV, MKV 등 (최대 500MB)</p>
      <input ref="fileInput" type="file" accept="video/*" @change="handleFileChange" class="hidden" />
    </div>

    <div v-if="store.selectedFile || store.selectedRemote" class="mt-6 p-4 bg-indigo-50 rounded-lg">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <span class="text-2xl">🎬</span>
          <div>
            <p class="font-medium text-gray-800">{{ store.selectedFile ? store.selectedFile.name : store.selectedRemote.title }}</p>
            <p v-if="store.selectedFile" class="text-sm text-gray-600">{{ (store.selectedFile.size / 1024 / 1024).toFixed(2) }} MB</p>
            <p v-else class="text-sm text-gray-600">{{ store.selectedRemote.sizeBytes ? (store.selectedRemote.sizeBytes/1024/1024).toFixed(2)+' MB' : '원격 미디어' }}</p>
          </div>
        </div>
        <button @click="store.setFile(null); store.selectedRemote = null" class="text-red-500 hover:text-red-700 font-medium">제거</button>
      </div>
    </div>

    <div class="mt-6">
      <label class="block text-sm font-medium text-gray-700 mb-2">언어 선택</label>
      <select v-model="store.selectedLanguage" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent">
        <option v-for="lang in languages" :key="lang.code" :value="lang.code">{{ lang.name }}</option>
      </select>
    </div>

  <div class="mt-6">
    <label class="block text-sm font-medium text-gray-700 mb-2">전사 모드</label>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <button
        class="p-4 rounded-xl border transition-all text-left"
        :class="store.selectedModel === 'cheetah' ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'"
        @click.prevent="store.selectedModel = 'cheetah'"
      >
        <div class="text-3xl mb-2">🐆</div>
        <div class="font-semibold">치타</div>
        <div class="text-sm text-gray-500">⚡ 가장 빠름 (tiny)</div>
      </button>

      <button
        class="p-4 rounded-xl border transition-all text-left"
        :class="store.selectedModel === 'dolphin' ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'"
        @click.prevent="store.selectedModel = 'dolphin'"
      >
        <div class="text-3xl mb-2">🐬</div>
        <div class="font-semibold">돌고래</div>
        <div class="text-sm text-gray-500">⚖️ 균형 (base)</div>
      </button>

      <button
        class="p-4 rounded-xl border transition-all text-left"
        :class="store.selectedModel === 'whale' ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'"
        @click.prevent="store.selectedModel = 'whale'"
      >
        <div class="text-3xl mb-2">🐋</div>
        <div class="font-semibold">고래</div>
        <div class="text-sm text-gray-500">⭐ 가장 정확 (small/↑)</div>
      </button>
    </div>
  </div>
  <div class="mt-6">
    <button type="button" @click="advancedOpen = !advancedOpen" class="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg">
      <span class="flex items-center space-x-2 text-gray-800 font-semibold">
        <span class="text-xl">👥</span>
          <span>화자 인식 및 추가 설정</span>
      </span>
      <span :class="['transition-transform', advancedOpen ? 'rotate-180' : 'rotate-0']">⌄</span>
    </button>
    <div v-if="advancedOpen" class="px-4 py-4 border border-t-0 border-gray-200 rounded-b-lg space-y-4">
      <label class="flex items-start space-x-3">
        <input type="checkbox" v-model="store.enableDiarization" class="mt-1 h-4 w-4 text-indigo-600 border-gray-300 rounded" />
        <span>
          <span class="font-medium text-gray-800">화자 인식</span>
          <p class="text-sm text-gray-500">화자 수를 자동으로 감지해 각 섹션에 ‘화자 N’ 레이블을 붙입니다.</p>
        </span>
      </label>
    </div>
  </div>
    <button @click="startTranscription" :disabled="!store.selectedFile && !store.selectedRemote" class="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-4 rounded-lg transition-colors duration-200 text-lg">
      {{ (store.selectedFile || store.selectedRemote) ? '🚀 전사 시작' : '파일을 선택해주세요' }}
    </button>
  </div>
</template>