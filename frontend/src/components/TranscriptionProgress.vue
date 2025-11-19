<script setup>
import { useTranscriptionStore } from '../stores/transcription'
const store = useTranscriptionStore()
</script>

<template>
  <div class="bg-white rounded-2xl shadow-xl p-8">
    <div class="text-center mb-6">
      <div class="inline-block animate-bounce text-6xl mb-4">⚡</div>
      <h2 class="text-2xl font-bold text-gray-800 mb-2">전사 진행 중</h2>
      <p class="text-gray-600">{{ store.statusMessage }}</p>
    </div>

    <div class="w-full bg-gray-200 rounded-full h-4 mb-4 overflow-hidden">
      <div class="bg-gradient-to-r from-indigo-500 to-purple-600 h-4 rounded-full transition-all duration-500 ease-out" :style="{ width: `${store.progress}%` }"></div>
    </div>

    <p class="text-center text-2xl font-bold text-indigo-600">{{ store.progress }}%</p>

    <div class="mt-8 space-y-3">
      <div class="flex items-center space-x-3" :class="store.progress >= 10 ? 'text-green-600' : 'text-gray-400'">
        <span class="text-2xl">{{ store.progress >= 10 ? '✅' : '⏳' }}</span>
        <span class="font-medium">동영상 업로드 완료</span>
      </div>
      <div class="flex items-center space-x-3" :class="store.progress >= 30 ? 'text-green-600' : 'text-gray-400'">
        <span class="text-2xl">{{ store.progress >= 30 ? '✅' : '⏳' }}</span>
        <span class="font-medium">오디오 추출 완료</span>
      </div>
      <div class="flex items-center space-x-3" :class="store.progress >= 90 ? 'text-green-600' : 'text-gray-400'">
        <span class="text-2xl">{{ store.progress >= 90 ? '✅' : '⏳' }}</span>
        <span class="font-medium">음성 인식 진행 중...</span>
      </div>
    </div>

    <button @click="store.reset()" class="w-full mt-8 border-2 border-gray-300 hover:border-red-500 hover:text-red-500 font-medium py-3 rounded-lg transition-colors duration-200">
      취소
    </button>
  </div>
</template>