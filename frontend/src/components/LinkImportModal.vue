<script setup>
// 링크에서 전사 시작을 위한 모달 컴포넌트
// - YouTube/Drive/Dropbox/Vimeo/X 등 공개 링크를 입력 받아 전사 시작
import { ref } from 'vue'
import { useTranscriptionStore } from '../stores/transcription'

const emit = defineEmits(['close'])
const store = useTranscriptionStore()
const url = ref('')
const isSync = ref(false) // 유지하되, 기본 흐름은 비동기 다운로드만

const start = async () => {
  const trimmed = (url.value || '').trim()
  if (!trimmed) return
  // 새로운 흐름: 먼저 링크를 다운로드만 수행
  await store.fetchMediaFromUrl(trimmed)
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="$emit('close')"></div>
    <div class="relative bg-white w-full max-w-lg rounded-2xl shadow-2xl p-6 mx-4">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center space-x-2">
          <span>🔗</span>
          <h4 class="text-xl font-bold">링크에서 가져오기</h4>
        </div>
        <button class="text-gray-500 hover:text-gray-700" @click="$emit('close')">✕</button>
      </div>

      <!-- 지원 플랫폼 이모지 행 (시각적 안내) -->
      <div class="flex items-center gap-2 mb-3 text-2xl select-none">
        <span title="YouTube">▶️</span>
        <span title="Dropbox">📦</span>
        <span title="Google Drive">🟩</span>
        <span title="Vimeo">🎞️</span>
        <span title="X">❌</span>
        <span title="기타">🔗</span>
      </div>

      <label class="block text-sm font-medium text-gray-700 mb-2">미디어 링크</label>
      <input v-model="url" :disabled="store.linkFetching" type="text" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100" placeholder="https://... (공개로 접근 가능한 링크)" />

      <div class="flex items-center justify-between mt-4">
        <label class="flex items-center space-x-2 text-sm text-gray-600">
          <input type="checkbox" v-model="isSync" class="h-4 w-4 text-indigo-600 border-gray-300 rounded" />
          <span>동기 모드로 실행</span>
        </label>
        <div class="flex gap-2">
          <button class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50" @click="$emit('close')" :disabled="store.linkFetching">취소</button>
          <button class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg disabled:bg-gray-400" :disabled="store.linkFetching" @click="start">
            <template v-if="!store.linkFetching">+ 가져오기</template>
            <template v-else>가져오는 중... {{ Math.max(0, Math.min(100, Math.round(store.linkFetchProgress||0))) }}%</template>
          </button>
        </div>
      </div>
    </div>
  </div>
  
</template>


