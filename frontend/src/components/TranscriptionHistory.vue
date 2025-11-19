<script setup>
import { useTranscriptionStore } from '../stores/transcription'
import { ref, computed, watch } from 'vue'
const store = useTranscriptionStore()

const formatDate = (iso) => new Date(iso).toLocaleString('ko-KR')
const openItem = (item) => {
  store.openResult(item)
}

const deleteItem = async (id) => {
  if (!confirm('이 전사 기록을 삭제할까요? (텍스트/SRT 파일 포함)')) return
  await store.deleteTranscription(id)
}

// 상태 판별 (결과 텍스트가 있고 에러가 없으면 완료)
const isSuccess = (item) => !!(item?.result && typeof item.result.text === 'string' && !item.error)
const statusTip = (item) => {
  if (isSuccess(item)) return '전사 완료'
  return item?.error ? String(item.error) : '전사 실패'
}

// 섹션 제목: 선택된 카테고리 반영 (이모지 포함)
const sectionTitle = computed(() => {
  const id = store.selectedCategoryId
  if (id === 'all') return '🗂️ 최근 전사 기록'
  if (id === 'uncategorized') return '📄 미분류'
  const c = store.categories.find((x) => x.id === id)
  return `${(c?.emoji || '📁')} ${c?.name || '최근 전사 기록'}`
})

// 검색 상태: 아이콘 클릭으로 모달 열기
const showSearch = ref(false)
const searchQuery = ref('')
const searchInputRef = ref(null)
const openSearch = () => {
  showSearch.value = true
  // 다음 틱에 포커스
  setTimeout(() => searchInputRef.value?.focus(), 0)
}
const closeSearch = () => {
  showSearch.value = false
}

// 현재 카테고리(또는 전체) 내 파일명/전사 텍스트 검색
const makeSnippet = (text, index, len) => {
  const start = Math.max(0, index - 60)
  const end = Math.min(text.length, index + len + 120)
  const prefix = start > 0 ? '…' : ''
  const suffix = end < text.length ? '…' : ''
  return prefix + text.slice(start, end).trim() + suffix
}
const searchResults = computed(() => {
  const base = store.filteredHistory || []
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  const results = []
  for (const item of base) {
    const name = String(item.filename || '')
    const fullText = String(item.result?.text || '')
    const idxName = name.toLowerCase().indexOf(q)
    const idxText = fullText.toLowerCase().indexOf(q)
    if (idxName >= 0 || idxText >= 0) {
      const snippet = idxText >= 0
        ? makeSnippet(fullText, idxText, q.length)
        : makeSnippet(name, idxName, q.length)
      results.push({ item, snippet })
    }
  }
  return results
})

// 페이지네이션 상태 (검색 결과 기준) - 본문 테이블용
const pageSize = 5
const currentPage = ref(1)
const filteredBySearch = computed(() => {
  const base = store.filteredHistory || []
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return base
  return base.filter((item) => {
    const name = String(item.filename || '').toLowerCase()
    const fullText = String(item.result?.text || '').toLowerCase()
    return name.includes(q) || fullText.includes(q)
  })
})
const totalItems = computed(() => (filteredBySearch.value.length))
const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))
const pagedHistory = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredBySearch.value.slice(start, start + pageSize)
})

const goPrev = () => {
  if (currentPage.value > 1) currentPage.value -= 1
}
const goNext = () => {
  if (currentPage.value < totalPages.value) currentPage.value += 1
}

// 히스토리/선택된 카테고리/검색 변경 시 페이지 리셋 및 범위 보정
watch(
  () => [store.filteredHistory?.length, store.selectedCategoryId, searchQuery.value],
  () => {
    if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
    if (currentPage.value < 1) currentPage.value = 1
    currentPage.value = 1
  }
)
</script>

<template>
  <div v-if="store.filteredHistory && store.filteredHistory.length" class="bg-white rounded-2xl shadow-xl p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-xl font-bold text-gray-800">{{ sectionTitle }}</h3>
      <div class="flex items-center space-x-2">
        <button class="text-gray-600 hover:text-gray-800 text-xl" @click="openSearch">🔍</button>
        <button class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg" @click="store.openUploadModal()">+ 파일 전사</button>
      </div>
    </div>

    <!-- 테이블 목록 (가로 스크롤 제거: 고정 레이아웃/열 폭 지정) -->
    <div class="rounded-lg border border-gray-200">
      <table class="w-full table-fixed text-left">
        <colgroup>
          <col class="w-[55%]" />
          <col class="w-[22%]" />
          <col class="w-[8%]" />
          <col class="w-[7%]" />
          <col class="w-[8%]" />
        </colgroup>
        <thead class="text-xs uppercase text-gray-500 bg-gray-50">
          <tr>
            <th class="px-4 py-3 whitespace-nowrap">이름</th>
            <th class="px-4 py-3 whitespace-nowrap">생성일</th>
            <th class="px-4 py-3 whitespace-nowrap">언어</th>
            <th class="px-4 py-3 whitespace-nowrap">상태</th>
            <th class="px-4 py-3 whitespace-nowrap text-right">작업</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in pagedHistory"
            :key="item.id"
            class="hover:bg-gray-50 cursor-pointer border-t border-gray-100"
            @click="openItem(item)"
          >
            <td class="px-4 py-3 font-medium text-gray-800 truncate">{{ item.filename }}</td>
            <td class="px-4 py-3 text-gray-600 whitespace-nowrap">{{ formatDate(item.timestamp) }}</td>
            <td class="px-4 py-3 whitespace-nowrap">{{ (item.language || 'ko').toUpperCase() }}</td>
            <td class="px-4 py-3 whitespace-nowrap relative group">
              <div class="inline-flex items-center" :class="isSuccess(item) ? 'text-green-600' : 'text-red-600'">
                <span class="w-2 h-2 rounded-full mr-2" :class="isSuccess(item) ? 'bg-green-500' : 'bg-red-500'"></span>
                {{ isSuccess(item) ? '완료' : '실패' }}
              </div>
              <!-- hover tooltip below status -->
              <div class="absolute left-0 top-full mt-2 z-10 hidden group-hover:block">
                <div class="bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 shadow-sm text-sm font-medium text-gray-800 inline-flex items-center">
                  <span class="mr-2" :class="isSuccess(item) ? 'text-green-600' : 'text-red-600'">{{ isSuccess(item) ? '✓' : '✗' }}</span>
                  {{ statusTip(item) }}
                </div>
                <div class="w-0 h-0 border-l-6 border-l-transparent border-r-6 border-r-transparent border-b-8 border-b-gray-50 ml-4 -mt-1"></div>
              </div>
            </td>
            <td class="px-4 py-3 text-right whitespace-nowrap">
              <button class="text-sm text-red-500 hover:text-red-700" @click.stop="deleteItem(item.id)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 페이징 처리 (5개 이상의 항목이 있는 경우에만 해당) -->
    <div v-if="totalItems > pageSize" class="mt-4 flex items-center justify-between">
      <button
        class="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-50"
        :disabled="currentPage === 1"
        @click="goPrev"
      >이전</button>

      <div class="text-sm text-gray-600">
        페이지 {{ currentPage }} / {{ totalPages }}
        <span class="ml-2">(총 {{ totalItems }}건)</span>
      </div>

      <button
        class="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-50"
        :disabled="currentPage === totalPages"
        @click="goNext"
      >다음</button>
    </div>

    <!-- 검색 모달 (결과 포함) -->
    <div v-if="showSearch" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/40" @click="closeSearch"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-2xl shadow-2xl p-6 mx-4 max-h-[80vh] overflow-hidden">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-2">
            <span>🔍</span>
            <h4 class="text-xl font-bold">전사 검색</h4>
          </div>
          <button class="text-gray-500 hover:text-gray-700" @click="closeSearch">✕</button>
        </div>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          class="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-transparent mb-3"
          placeholder="전사를 검색하세요..."
        />
        <div v-if="searchQuery.trim().length === 0" class="text-gray-500 text-sm">검색어를 입력하세요.</div>
        <div v-else class="text-gray-600 text-sm mb-3"><span class="font-semibold">{{ searchQuery }}</span>에 대한 결과를 표시 중입니다.</div>
        <div class="overflow-y-auto space-y-3 pr-1" style="max-height: 50vh;">
          <div
            v-for="res in searchResults"
            :key="res.item.id"
            class="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 cursor-pointer"
            @click="openItem(res.item); closeSearch()"
          >
            <div class="font-medium text-gray-800 truncate">{{ res.item.filename }}</div>
            <div class="text-xs text-gray-500 mb-1">{{ formatDate(res.item.timestamp) }} · {{ (res.item.language || 'ko').toUpperCase() }}</div>
            <div class="text-sm text-gray-700 line-clamp-3">{{ res.snippet }}</div>
          </div>
          <div v-if="searchResults.length === 0" class="text-gray-500 text-sm">검색 결과가 없습니다.</div>
        </div>
      </div>
    </div>
  </div>
</template>