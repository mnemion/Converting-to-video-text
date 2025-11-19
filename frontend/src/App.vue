<script setup>
import FileUpload from './components/FileUpload.vue'
import TranscriptionProgress from './components/TranscriptionProgress.vue'
import TranscriptionResult from './components/TranscriptionResult.vue'
import TranscriptionHistory from './components/TranscriptionHistory.vue'
import CategoriesPanel from './components/CategoriesPanel.vue'
import GlobalAudioPlayer from './components/GlobalAudioPlayer.vue'
import LinkImportModal from './components/LinkImportModal.vue'
import { useTranscriptionStore } from './stores/transcription'

const store = useTranscriptionStore()
store.loadHistory?.()
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <div class="container mx-auto px-4 py-8">
      <header class="mb-6">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
          <div class="text-center md:text-left flex-1">
            <h1 class="text-4xl font-bold text-gray-800 mb-1">🎥 동영상 텍스트 전사</h1>
            <p class="text-gray-600">동영상을 업로드하면 AI가 자동으로 음성을 텍스트로 변환합니다</p>
          </div>
        </div>
      </header>

      <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-5 gap-6">
        <div class="md:col-span-1 order-2 md:order-1">
          <CategoriesPanel />
        </div>
        <div class="md:col-span-4 order-1 md:order-2">
          <!-- 업로드는 모달에서 진행, 본문에는 진행/결과 또는 목록만 표시 -->
          <TranscriptionProgress v-if="store.isProcessing" />
          <TranscriptionResult v-else-if="store.hasResult" />
          <TranscriptionHistory v-else />

          <div v-if="store.error" class="mt-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <p class="font-medium">❌ {{ store.error }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 파일 전사 모달 (전역 상태) -->
    <div v-if="store.showUploadModal" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/40" @click="store.closeUploadModal()"></div>
      <div class="relative bg-white w-full max-w-3xl rounded-2xl shadow-2xl p-6 mx-4">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span>📤</span>
            <h4 class="text-xl font-bold">파일 전사</h4>
          </div>
          <button class="mr-2 text-indigo-600 hover:text-indigo-800" @click="store.openLinkModal()" title="링크에서 가져오기">🔗</button>
          <button class="text-gray-500 hover:text-gray-700" @click="store.closeUploadModal()">✕</button>
        </div>
        <FileUpload />
      </div>
    </div>
    <LinkImportModal v-if="store.showLinkModal" @close="store.closeLinkModal()" />
    <GlobalAudioPlayer />
  </div>
</template>