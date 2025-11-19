import { defineStore } from 'pinia'
import axios from 'axios'

export const useTranscriptionStore = defineStore('transcription', {
  state: () => ({
    selectedFile: null,
    selectedLanguage: 'ko',
    selectedModel: 'dolphin', // 모델 프리셋: cheetah | dolphin | whale
    isProcessing: false,
    currentTaskId: null,
    progress: 0,
    statusMessage: '',
    transcriptionResult: null,
    error: null,
    history: [],
    enableDiarization: false,
    // 카테고리 상태
    categories: [], // 구조: { id, name, createdAt, emoji }
    selectedCategoryId: 'all', // 'all' | 'uncategorized' | 카테고리 id
    // 업로드 시작 시 선택한 카테고리 임시 저장
    pendingCategoryIdForNewItem: null,
    // 업로드 모달 표시 상태 (전역)
    showUploadModal: false,
    showLinkModal: false,
    // 링크 다운로드(가져오기) 진행 상태
    linkFetchTaskId: null,
    linkFetchProgress: 0,
    linkFetching: false,
    // 링크로 가져온 항목 선택 상태
    selectedRemote: null, // { jobId, title, sizeBytes }
    // URL 리스너 1회 등록용
    urlListenerAttached: false,
    // 전사 보기 옵션
    showTimestampsInView: false,
    showSpeakersInView: true,
    // 공유 보기 모드
    sharedMode: false,
    sharedByEmail: '',
    // 오디오 동기화 상태
    audioCurrentTime: 0,
    audioIsPlaying: false,
    followPlayback: false, // 자동 스크롤 여부(기본 OFF)
  }),
  getters: {
    hasResult: (state) => state.transcriptionResult !== null,
    isUploading: (state) => state.isProcessing && state.progress < 10,
    isTranscribing: (state) => state.isProcessing && state.progress >= 10,
    // 선택한 카테고리 기준으로 필터링
    filteredHistory: (state) => {
      if (state.selectedCategoryId === 'all') return state.history
      if (state.selectedCategoryId === 'uncategorized') {
        return state.history.filter((h) => !h.categoryId)
      }
      return state.history.filter((h) => h.categoryId === state.selectedCategoryId)
    },
    // 좌측 패널 뱃지용 개수
    categoryCounts: (state) => {
      const counts = { all: state.history.length, uncategorized: 0 }
      for (const c of state.categories) counts[c.id] = 0
      for (const h of state.history) {
        if (!h.categoryId) counts.uncategorized += 1
        else counts[h.categoryId] = (counts[h.categoryId] || 0) + 1
      }
      return counts
    },
  },
  actions: {
    // 화자 라벨 보기 토글
    toggleSpeakersInView() {
      this.showSpeakersInView = !this.showSpeakersInView
    },
    // 보기 옵션
    toggleTimestamps() {
      this.showTimestampsInView = !this.showTimestampsInView
    },
    // 공유 (간단: 현재 URL 클립보드 복사)
    async shareCurrent() {
      try {
        await navigator.clipboard.writeText(window.location.href)
        this.statusMessage = '링크 복사됨'
      } catch {
        this.statusMessage = '링크 복사 실패'
      }
    },
    // 전사 편집 저장 (백엔드 업데이트 + 로컬 히스토리 동기화)
    async saveEditedTranscript(jobId, newText) {
      await axios.put(`/api/transcription/${jobId}/text`, { text: newText })
      const item = this.history.find((h) => h.id === jobId)
      const now = new Date().toISOString()
      if (item) {
        item.result.text = newText
        item.result.editedAt = now
      }
      if (this.transcriptionResult?.job_id === jobId) {
        this.transcriptionResult.text = newText
        this.transcriptionResult.editedAt = now
      }
      this.saveHistory()
    },
    // 파일 이름 변경 (히스토리 메타만 변경)
    renameCurrentFile(jobId, newName) {
      const item = this.history.find((h) => h.id === jobId)
      if (item) item.filename = newName
      this.saveHistory()
    },
    // 이동(카테고리 변경)
    moveCurrentToCategory(jobId, categoryId) {
      this.assignItemToCategory(jobId, categoryId)
    },
    // 오디오 다운로드 URL
    getAudioDownloadUrl(jobId) {
      return `/api/export/audio/${jobId}`
    },
    // 오디오 재생 상태 보고/제어
    reportAudioTime(sec) {
      this.audioCurrentTime = Number.isFinite(sec) ? sec : 0
    },
    reportAudioPlaying(is) {
      this.audioIsPlaying = !!is
    },
    toggleFollowPlayback() {
      this.followPlayback = !this.followPlayback
    },
    // 전역 오디오 엘리먼트 제어를 위한 커스텀 이벤트 브리지
    seekGlobalAudioTo(sec) {
      try {
        window.dispatchEvent(new CustomEvent('app-audio-seek', { detail: { time: Math.max(0, sec || 0) } }))
      } catch {}
    },
    // 삭제는 기존 deleteTranscription 사용

    // URL 동기화 헬퍼 (기본: pushState로 히스토리 쌓음)
    setUrlState(partial, options = { replace: false }) {
      try {
        const url = new URL(window.location.href)
        if (Object.prototype.hasOwnProperty.call(partial, 'cat')) {
          const v = partial.cat
          if (!v) url.searchParams.delete('cat')
          else url.searchParams.set('cat', String(v))
        }
        if (Object.prototype.hasOwnProperty.call(partial, 'job')) {
          const v = partial.job
          if (!v) url.searchParams.delete('job')
          else url.searchParams.set('job', String(v))
        }
        if (options.replace) window.history.replaceState({}, '', url.toString())
        else window.history.pushState({}, '', url.toString())
      } catch {}
    },
    attachUrlListener() {
      if (this.urlListenerAttached) return
      this.urlListenerAttached = true
      try {
        window.addEventListener('popstate', () => {
          try {
            const url = new URL(window.location.href)
            const cat = url.searchParams.get('cat') || 'all'
            const job = url.searchParams.get('job')
            const shared = url.searchParams.get('shared')
            const by = url.searchParams.get('by')
            // 카테고리 동기화
            if (this.selectedCategoryId !== cat) {
              this.selectedCategoryId = cat
              this.saveCategories()
            }
            // 결과 동기화
            if (job) {
              const found = this.history.find((h) => String(h.id) === String(job))
              if (found) {
                this.transcriptionResult = found.result
                this.isProcessing = false
                this.statusMessage = '기록 복원'
              }
            } else {
              this.transcriptionResult = null
            }
            if (shared) this.sharedMode = ['1','true','yes','on'].includes(shared.toLowerCase())
            this.sharedByEmail = by ? decodeURIComponent(by) : this.sharedByEmail
          } catch {}
        })
      } catch {}
    },
    initFromUrl() {
      try {
        const url = new URL(window.location.href)
        const cat = url.searchParams.get('cat')
        const job = url.searchParams.get('job')
        const shared = url.searchParams.get('shared')
        const by = url.searchParams.get('by')
        if (cat) this.selectedCategoryId = cat
        if (job) {
          const found = this.history.find((h) => String(h.id) === String(job))
          if (found) {
            this.transcriptionResult = found.result
            this.isProcessing = false
            this.statusMessage = '기록 복원'
          }
        }
        if (shared) this.sharedMode = ['1','true','yes','on'].includes(shared.toLowerCase())
        if (by) this.sharedByEmail = decodeURIComponent(by)
      } catch {}
    },

    openUploadModal() {
      this.showUploadModal = true
    },
    closeUploadModal() {
      this.showUploadModal = false
    },
    openLinkModal() {
      this.showLinkModal = true
    },
    closeLinkModal() {
      this.showLinkModal = false
    },
    async fetchMediaFromUrl(url) {
      // 링크를 백엔드에서 다운로드만 수행
      this.linkFetching = true
      this.linkFetchProgress = 0
      this.linkFetchTaskId = null
      this.error = null
      try {
        const payload = new URLSearchParams()
        payload.append('url', url)
        const { data } = await axios.post('/api/fetch-url-async', payload, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
        this.linkFetchTaskId = data.task_id
        // 진행률 폴링
        const poll = setInterval(async () => {
          try {
            const res = await axios.get(`/api/status/${this.linkFetchTaskId}`)
            const { state, progress, result, error } = res.data
            if (state === 'PROGRESS') {
              this.linkFetchProgress = progress || 0
            } else if (state === 'SUCCESS') {
              clearInterval(poll)
              this.linkFetchProgress = 100
              this.linkFetching = false
              // 선택 상태 세팅
              this.selectedRemote = {
                jobId: result?.job_id || data.job_id,
                title: result?.original_filename || 'link',
                sizeBytes: result?.size_bytes || null,
              }
              // 모달 닫기, 업로드 모달은 유지
              this.closeLinkModal()
              // 파일 선택 카드에 표시되도록 기존 파일 선택은 해제
              this.selectedFile = null
              this.statusMessage = '링크 가져오기 완료'
            } else if (state === 'FAILURE') {
              clearInterval(poll)
              this.linkFetching = false
              this.error = error || '링크 가져오기 실패'
            }
          } catch (e) {
            clearInterval(poll)
            this.linkFetching = false
            this.error = '링크 상태 확인 실패'
          }
        }, 1200)
      } catch (e) {
        this.linkFetching = false
        this.error = e?.response?.data?.detail || '링크 요청 실패'
      }
    },
    // 결과 열기(지속성 + URL)
    openResult(item) {
      this.transcriptionResult = item?.result || null
      this.isProcessing = false
      this.statusMessage = '기록 불러옴'
      try {
        if (item?.id) localStorage.setItem('transcriptionOpenResultId', String(item.id))
      } catch {}
      this.setUrlState({ job: item?.id })
    },
    restoreOpenResult() {
      try {
        const idFromUrl = new URL(window.location.href).searchParams.get('job')
        const id = idFromUrl || localStorage.getItem('transcriptionOpenResultId')
        if (!id) return
        const found = this.history.find((h) => String(h.id) === String(id))
        if (found) {
          this.transcriptionResult = found.result
          this.isProcessing = false
          this.statusMessage = '기록 복원'
        } else if (!idFromUrl) {
          localStorage.removeItem('transcriptionOpenResultId')
        }
      } catch {}
    },
    clearOpenResult() {
      this.transcriptionResult = null
      try { localStorage.removeItem('transcriptionOpenResultId') } catch {}
      this.setUrlState({ job: null })
    },
    setFile(file) {
      this.selectedFile = file
      this.error = null
    },
    setLanguage(language) {
      this.selectedLanguage = language
    },
    async startTranscriptionFromUrl(url, { mode = 'async' } = {}) {
      // 링크 기반 전사 시작 (기본 비동기)
      this.closeUploadModal()
      this.closeLinkModal()
      this.isProcessing = true
      this.progress = 0
      this.error = null
      this.transcriptionResult = null
      this.pendingCategoryIdForNewItem = this.selectedCategoryId

      try {
        const payload = new URLSearchParams()
        payload.append('url', url)
        payload.append('language', this.selectedLanguage)
        payload.append('model', this.resolveModelSize())
        if (this.enableDiarization) payload.append('diarize', 'true')

        if (mode === 'async') {
          const { data } = await axios.post('/api/transcribe-url-async', payload, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          })
          this.currentTaskId = data.task_id
          this.statusMessage = '작업이 시작되었습니다'
          this.pollTaskStatus()
        } else {
          const { data } = await axios.post('/api/transcribe-url', payload, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          })
          this.progress = 100
          this.transcriptionResult = data
          this.statusMessage = '전사 완료!'
          this.isProcessing = false
          this.addToHistory(data, this.pendingCategoryIdForNewItem)
          this.selectedFile = null
          try { localStorage.setItem('transcriptionOpenResultId', String(data.job_id)) } catch {}
          this.setUrlState({ job: data.job_id })
          this.pendingCategoryIdForNewItem = null
        }
      } catch (err) {
        this.error = err?.response?.data?.detail || '링크 처리 실패'
        this.isProcessing = false
      }
    },
    async startTranscription() {
      // 링크로 가져온 항목 우선 처리, 없으면 파일 업로드 처리
      this.error = null
      if (this.selectedRemote && this.selectedRemote.jobId) {
        this.closeUploadModal()
        this.isProcessing = true
        this.progress = 0
        this.transcriptionResult = null
        this.pendingCategoryIdForNewItem = this.selectedCategoryId
        try {
          const payload = new URLSearchParams()
          payload.append('job_id', this.selectedRemote.jobId)
          payload.append('language', this.selectedLanguage)
          payload.append('model', this.resolveModelSize())
          if (this.enableDiarization) payload.append('diarize', 'true')
          const { data } = await axios.post('/api/transcribe-downloaded-async', payload)
          this.currentTaskId = data.task_id
          this.statusMessage = '작업이 시작되었습니다'
          this.pollTaskStatus()
        } catch (err) {
          this.error = err?.response?.data?.detail || '전사 시작 실패'
          this.isProcessing = false
        }
        return
      }

      if (!this.selectedFile) {
        this.error = '파일을 선택해주세요'
        return
      }
      // 기존 파일 업로드 비동기 흐름
      this.closeUploadModal()
      this.isProcessing = true
      this.progress = 0
      this.transcriptionResult = null
      this.pendingCategoryIdForNewItem = this.selectedCategoryId

      const formData = new FormData()
      formData.append('file', this.selectedFile)
      formData.append('language', this.selectedLanguage)
      formData.append('model', this.resolveModelSize())
      try {
        if (this.enableDiarization) formData.append('diarize', 'true')
        const response = await axios.post('/api/transcribe-async', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        this.currentTaskId = response.data.task_id
        this.statusMessage = '작업이 시작되었습니다'
        this.pollTaskStatus()
      } catch (err) {
        this.error = err.response?.data?.detail || '업로드 실패'
        this.isProcessing = false
      }
    },
    resolveModelSize() {
      const map = {
        cheetah: 'tiny',     // 가장 빠름
        dolphin: 'base',     // 균형 잡힘
        whale: 'small',      // 더 높은 정확도 (CPU 기준), GPU면 medium/large 권장
      }
      return map[this.selectedModel] || 'base'
    },
    async pollTaskStatus() {
      const poll = setInterval(async () => {
        try {
          const response = await axios.get(`/api/status/${this.currentTaskId}`)
          const { state, progress, result, error } = response.data
          if (state === 'PROGRESS') {
            this.progress = progress || 0
            this.statusMessage = `처리 중... ${this.progress}%`
          } else if (state === 'SUCCESS') {
            clearInterval(poll)
            this.progress = 100
            this.transcriptionResult = result
            this.statusMessage = '전사 완료!'
            this.isProcessing = false
            this.addToHistory(result, this.pendingCategoryIdForNewItem)
            // 완료 후 이전 파일 선택 초기화
            this.selectedFile = null
            try { localStorage.setItem('transcriptionOpenResultId', String(result.job_id)) } catch {}
            this.setUrlState({ job: result.job_id })
            this.pendingCategoryIdForNewItem = null
          } else if (state === 'FAILURE') {
            clearInterval(poll)
            this.error = error || '전사 실패'
            this.isProcessing = false
          }
        } catch (err) {
          clearInterval(poll)
          this.error = '상태 확인 실패'
          this.isProcessing = false
        }
      }, 2000)
    },
    loadHistory() {
      try {
        const raw = localStorage.getItem('transcriptionHistory')
        if (raw) {
          const parsed = JSON.parse(raw)
          if (Array.isArray(parsed)) this.history = parsed
        }
      } catch {}
      // 카테고리 로드
      this.loadCategories()
      this.ensureSelectedCategoryValid()
      // URL 파라미터 초기화 적용
      this.initFromUrl()
      // 열려 있던 결과 복원 (URL 우선)
      this.restoreOpenResult()
      // 뒤로가기/앞으로가기 반영
      this.attachUrlListener()
    },
    saveHistory() {
      try {
        localStorage.setItem('transcriptionHistory', JSON.stringify(this.history))
      } catch {}
    },
    addToHistory(result, categoryIdParam) {
      const newItem = {
        id: result.job_id,
        // 파일 업로드가 아니면 서버에서 돌려준 제목/파일명을 사용
        filename: this.selectedFile?.name || result?.original_filename || 'link',
        language: this.selectedLanguage,
        timestamp: new Date().toISOString(),
        result,
      }
      // 시작 시 선택한 카테고리로 분류(단, all/미분류/무효 제외)
      if (
        categoryIdParam &&
        categoryIdParam !== 'all' &&
        categoryIdParam !== 'uncategorized' &&
        this.categories.some((c) => c.id === categoryIdParam)
      ) {
        newItem.categoryId = categoryIdParam
      }

      this.history.unshift(newItem)
      if (this.history.length > 10) {
        this.history = this.history.slice(0, 10)
      }
      this.saveHistory()
      this.ensureSelectedCategoryValid()
    },
    // 카테고리 저장/로드
    loadCategories() {
      try {
        const catsRaw = localStorage.getItem('transcriptionCategories')
        if (catsRaw) {
          const parsed = JSON.parse(catsRaw)
          if (Array.isArray(parsed)) this.categories = parsed.map((c) => ({ ...c, emoji: c.emoji || '📁' }))
        }
        const selRaw = localStorage.getItem('transcriptionSelectedCategory')
        if (selRaw) this.selectedCategoryId = selRaw
      } catch {}
    },
    saveCategories() {
      try {
        localStorage.setItem('transcriptionCategories', JSON.stringify(this.categories))
        localStorage.setItem('transcriptionSelectedCategory', this.selectedCategoryId)
      } catch {}
    },
    selectCategory(categoryId) {
      this.selectedCategoryId = categoryId
      this.saveCategories()
      // 카테고리 전환 시 결과 화면을 닫고 URL 갱신 (히스토리 쌓기)
      this.clearOpenResult()
      this.setUrlState({ cat: categoryId, job: null })
    },
    createCategory(name) {
      const id = `cat_${Date.now()}`
      this.categories.push({ id, name: name?.trim() || '새 폴더', createdAt: new Date().toISOString(), emoji: '📁' })
      this.saveCategories()
      return id
    },
    renameCategory(id, name) {
      const c = this.categories.find((x) => x.id === id)
      if (c) {
        c.name = name?.trim() || c.name
        this.saveCategories()
      }
    },
    setCategoryEmoji(id, emoji) {
      const c = this.categories.find((x) => x.id === id)
      if (c) {
        c.emoji = emoji || '📁'
        this.saveCategories()
      }
    },
    deleteCategory(id) {
      this.categories = this.categories.filter((c) => c.id !== id)
      // 카테고리 제거 시 항목은 미분류로 이동
      for (const h of this.history) {
        if (h.categoryId === id) delete h.categoryId
      }
      // 선택된 카테고리가 삭제되면 all로 복귀
      if (this.selectedCategoryId === id) this.selectedCategoryId = 'all'
      this.saveCategories()
      this.saveHistory()
      this.ensureSelectedCategoryValid()
    },
    assignItemToCategory(itemId, categoryId) {
      const item = this.history.find((h) => h.id === itemId)
      if (!item) return
      if (!categoryId || categoryId === 'uncategorized') delete item.categoryId
      else item.categoryId = categoryId
      this.saveHistory()
      this.ensureSelectedCategoryValid()
    },
    async deleteTranscription(jobId) {
      // 백엔드 파일(txt/srt) 삭제 요청 + 로컬 히스토리 제거
      try {
        await axios.delete(`/api/transcription/${jobId}`)
      } catch (e) {
        // 서버 오류여도 로컬 UI 정리는 진행 (파일이 없을 수 있음)
      }
      this.history = this.history.filter((h) => h.id !== jobId)
      // 현재 화면이 방금 삭제한 항목이면 결과 화면 초기화
      if (this.transcriptionResult?.job_id === jobId) {
        this.clearOpenResult()
      }
      this.saveHistory()
      this.ensureSelectedCategoryValid()
    },
    ensureSelectedCategoryValid() {
      // 결과 화면이 열려 있으면 카테고리 자동 전환을 하지 않음
      if (this.transcriptionResult) return
      // 미분류가 비면 자동으로 전체로 이동
      const uncatCount = this.categoryCounts?.uncategorized || 0
      if (this.selectedCategoryId === 'uncategorized' && uncatCount === 0) {
        // 결과가 열려 있지 않을 때만 자동 전환
        this.selectCategory('all')
      }
      // 선택된 카테고리가 삭제되었으면 전체로 복귀
      if (
        this.selectedCategoryId !== 'all' &&
        this.selectedCategoryId !== 'uncategorized' &&
        !this.categories.some((c) => c.id === this.selectedCategoryId)
      ) {
        this.selectCategory('all')
      }
    },
    reset() {
      this.selectedFile = null
      this.selectedRemote = null
      this.isProcessing = false
      this.currentTaskId = null
      this.progress = 0
      this.statusMessage = ''
      this.transcriptionResult = null
      this.error = null
      try { localStorage.removeItem('transcriptionOpenResultId') } catch {}
      this.setUrlState({ job: null })
    },
    getDownloadUrl(filepath) {
      return `http://localhost:8000/${filepath}`
    },
  },
})