<script setup>
import { ref, onMounted } from 'vue'
import { useTranscriptionStore } from '../stores/transcription'
const store = useTranscriptionStore()

const showModal = ref(false)
const newName = ref('')
const inputRef = ref(null)

const openModal = () => {
  showModal.value = true
  newName.value = ''
  setTimeout(() => inputRef.value?.focus(), 0)
}
const closeModal = () => {
  showModal.value = false
}
const confirmCreate = () => {
  const id = store.createCategory(newName.value)
  store.selectCategory(id)
  closeModal()
}

const onRename = (id) => {
  const name = prompt('새 이름을 입력하세요', '')
  if (name !== null) store.renameCategory(id, name)
}
const onDelete = (id) => {
  if (confirm('이 카테고리를 삭제하시겠습니까? 항목은 미분류로 이동합니다.')) {
    store.deleteCategory(id)
  }
}

const onKey = (e) => {
  if (!showModal.value) return
  if (e.key === 'Escape') closeModal()
}
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKey)
}

// 카테고리 행 우측 액션 제거됨
</script>

<template>
  <aside class="sticky top-6 max-h-[calc(100vh-24px)] overflow-auto">
    <div>
      <div class="bg-white rounded-2xl shadow-xl p-4">
        <h3 class="text-lg font-bold text-gray-800 mb-3">바로가기</h3>

        <div class="space-y-1">
          <!-- 전체(최근 파일) -->
          <div class="flex items-center">
            <button
              class="flex-1 flex items-center justify-between px-3 py-2 rounded hover:bg-gray-100"
              :class="store.selectedCategoryId === 'all' ? 'bg-gray-100' : ''"
              @click="store.selectCategory('all')"
            >
              <span class="flex items-center space-x-2">
                <span>🗂️</span>
                <span class="whitespace-nowrap">최근 파일</span>
              </span>
              <span class="text-sm text-gray-500 whitespace-nowrap">{{ store.categoryCounts.all || 0 }}</span>
            </button>
          </div>

          <div class="mt-2 text-gray-700 text-sm">폴더</div>

          <!-- 미분류 (개수 있을 때만 표시) -->
          <div v-if="store.categoryCounts.uncategorized > 0" class="flex items-center">
            <button
              class="flex-1 flex items-center justify-between px-3 py-2 rounded hover:bg-gray-100"
              :class="store.selectedCategoryId === 'uncategorized' ? 'bg-gray-100' : ''"
              @click="store.selectCategory('uncategorized')"
            >
              <span class="flex items-center space-x-2">
                <span>📄</span>
                <span class="whitespace-nowrap">미분류</span>
              </span>
              <span class="text-sm text-gray-500 whitespace-nowrap">{{ store.categoryCounts.uncategorized || 0 }}</span>
            </button>
          </div>

          <!-- 사용자 폴더 목록 -->
          <div v-for="c in store.categories" :key="c.id" class="flex items-center">
            <button
              class="flex-1 flex items-center justify-between px-3 py-2 rounded hover:bg-gray-100"
              :class="store.selectedCategoryId === c.id ? 'bg-gray-100' : ''"
              @click="store.selectCategory(c.id)"
            >
              <span class="flex items-center space-x-2 truncate" :title="c.name">
                <span>{{ c.emoji || '📁' }}</span>
                <span class="truncate">{{ c.name }}</span>
              </span>
              <span class="text-sm text-gray-500 whitespace-nowrap">{{ store.categoryCounts[c.id] || 0 }}</span>
            </button>
          </div>

          <div class="mt-2">
            <button class="w-full px-3 py-2 border rounded hover:bg-gray-50" @click="openModal">+ 새 폴더</button>
          </div>
        </div>
      </div>

      <!-- 기존 새 폴더 모달은 아래 유지 -->
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/40" @click="closeModal"></div>
        <div class="relative bg-white w-full max-w-md rounded-2xl shadow-2xl p-6 mx-4">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2">
              <span>➕</span>
              <h4 class="text-xl font-bold">새 폴더</h4>
            </div>
            <button class="text-gray-500 hover:text-gray-700" @click="closeModal">✕</button>
          </div>
          <p class="text-gray-600 mb-4">폴더는 관련된 파일들을 함께 묶습니다.</p>
          <label class="block text-sm font-medium text-gray-700 mb-1">폴더 이름</label>
          <input
            ref="inputRef"
            v-model="newName"
            class="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-transparent mb-4"
            placeholder="폴더 이름"
            @keyup.enter="confirmCreate"
          />
          <button
            class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg"
            @click="confirmCreate"
          >폴더 만들기</button>
        </div>
      </div>
    </div>
  </aside>
</template>