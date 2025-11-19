<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useTranscriptionStore } from '../stores/transcription'
const store = useTranscriptionStore()

// 현재 전사 항목
const currentItem = computed(() => {
  const id = store.transcriptionResult?.job_id
  return store.history.find((h) => h.id === id) || null
})

const titleText = computed(() => currentItem.value?.filename || '전사 결과')
const createdAt = computed(() => {
  const ts = currentItem.value?.timestamp
  if (!ts) return ''
  try { return new Date(ts).toLocaleString('ko-KR') } catch { return ts }
})

// 타임스탬프 표시용 SRT 로딩
const srtLoading = ref(false)
const srtError = ref('')
const srtEntries = ref([])
const srtLoadedFor = ref(null)
const srtContainerRef = ref(null)
const activeEl = ref(null)

const getSrtUrl = () => {
  const path = store.transcriptionResult?.srt_file || `outputs/${store.transcriptionResult?.job_id}.srt`
  return path ? store.getDownloadUrl(path) : null
}

const parseSrt = (raw) => {
  const lines = raw.split(/\r?\n/)
  const entries = []
  let i = 0
  const timeRe = /(\d{2}:\d{2}:\d{2}),\d{1,3}\s*-->\s*(\d{2}:\d{2}:\d{2}),\d{1,3}/
  while (i < lines.length) {
    let line = lines[i].trim()
    if (!line) { i++; continue }
    // 번호 라인은 무시
    if (/^\d+$/.test(line)) { i++; continue }
    const m = line.match(timeRe)
    if (m) {
      const start = m[1]
      const end = m[2]
      i++
      const textLines = []
      while (i < lines.length && lines[i].trim() !== '') {
        textLines.push(lines[i].trim())
        i++
      }
      let text = textLines.join(' ')
      // 화자 라벨 추출: [화자 N] / [SPEAKER_1] / '화자 N:' / 'SPEAKER 1:'
      let speaker = null
      let msp = text.match(/^\[(?:\s*화자\s*(\d+)|\s*SPEAKER[_\s]*(\d+))\]\s*(.*)$/i)
      if (msp) {
        speaker = Number(msp[1] || msp[2])
        text = msp[3].trim()
      } else {
        msp = text.match(/^(?:\s*화자\s*(\d+)|\s*SPEAKER[_\s]*(\d+))\s*:\s*(.*)$/i)
        if (msp) {
          speaker = Number(msp[1] || msp[2])
          text = msp[3].trim()
        }
      }
      const ent = { start, end, text }
      if (speaker) ent.speaker = speaker
      entries.push(ent)
    }
    i++
  }
  return entries
}

// 화자 라벨 사용 가능 여부 (백엔드 응답/파싱 결과 기반)
const hasSpeakerLabels = computed(() => {
  if (Array.isArray(store.transcriptionResult?.speakers) && store.transcriptionResult.speakers.length > 0) return true
  if (Array.isArray(srtEntries.value) && srtEntries.value.some(e => e && e.speaker)) return true
  return false
})
watch(hasSpeakerLabels, (v) => { if (!v) store.showSpeakersInView = false })

const loadSrt = async () => {
  const jobId = store.transcriptionResult?.job_id
  if (!jobId || srtLoadedFor.value === jobId) return
  const url = getSrtUrl()
  if (!url) return
  srtLoading.value = true
  srtError.value = ''
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new Error('SRT fetch failed')
    const raw = await res.text()
    srtEntries.value = parseSrt(raw)
    srtLoadedFor.value = jobId
  } catch (e) {
    srtError.value = '타임스탬프 로딩 실패'
  } finally {
    srtLoading.value = false
  }
}

// 기본 텍스트 가독성 향상을 위한 단락 분리(마침표/물음표/느낌표/개행 단위)
const segmentedPlain = computed(() => {
  const t = store.transcriptionResult?.text || ''
  const parts = t.split(/(?<=[。．\.！!？?\n])\s+/)
  return parts.map(s => s.trim()).filter(Boolean)
})

watch(() => store.showTimestampsInView, (v) => { if (v) { srtEntries.value = []; srtLoadedFor.value = null; loadSrt() } })
watch(() => store.transcriptionResult?.job_id, () => { srtEntries.value = []; srtLoadedFor.value = null; loadSrt() })
onMounted(() => { loadSrt() })

// 현재 시간과 일치하는 SRT 인덱스 계산
const toSec = (hhmmss) => {
  if (!hhmmss) return 0
  const [h, m, s] = hhmmss.split(':').map(Number)
  return (h || 0) * 3600 + (m || 0) * 60 + (s || 0)
}
const activeIndex = computed(() => {
  const t = store.audioCurrentTime || 0
  if (!srtEntries.value?.length) return -1
  for (let i = 0; i < srtEntries.value.length; i++) {
    const cur = srtEntries.value[i]
    const next = srtEntries.value[i+1]
    const start = toSec(cur.start)
    const end = next ? toSec(next.start) : (toSec(cur.end) || start + 5)
    if (t >= start && t < end) return i
  }
  return -1
})

// 활성 행 자동 스크롤
watch(activeIndex, async (idx) => {
  if (idx < 0) return
  await nextTick()
  try {
    const row = document.querySelector(`[data-srt-idx="${idx}"]`)
    activeEl.value = row || null
    if (!store.followPlayback) return
    if (row) {
      const rect = row.getBoundingClientRect()
      const headerOffset = 120
      const targetY = window.scrollY + rect.top - headerOffset
      window.scrollTo({ top: targetY, behavior: 'smooth' })
    }
  } catch {}
})

// SRT 클릭 시 오디오 시킹
const seekTo = (idx) => {
  const e = srtEntries.value?.[idx]
  if (!e) return
  store.seekGlobalAudioTo(toSec(e.start))
}

const downloadViaFetch = async (url, filename) => {
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new Error('download failed')
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 2000)
  } catch (e) {
    console.error('Download error:', e)
    // 폴백: 새 탭 열기
    const a = document.createElement('a')
    a.href = url
    a.target = '_blank'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }
}

const exportPdf = async (withTs = false) => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  const url = `/api/export/pdf/${id}?ts=${withTs ? 1 : 0}&spk=${store.showSpeakersInView && hasSpeakerLabels.value ? 1 : 0}`
  const name = `transcript_${id}${withTs ? '_ts' : ''}.pdf`
  await downloadViaFetch(url, name)
}
const exportDocx = async (withTs = false) => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  const url = `/api/export/docx/${id}?ts=${withTs ? 1 : 0}&spk=${store.showSpeakersInView && hasSpeakerLabels.value ? 1 : 0}`
  const name = `transcript_${id}${withTs ? '_ts' : ''}.docx`
  await downloadViaFetch(url, name)
}
const exportTxt = async (withTs = false) => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  const url = `/api/export/txt/${id}?ts=${withTs ? 1 : 0}&spk=${store.showSpeakersInView && hasSpeakerLabels.value ? 1 : 0}`
  const name = `transcript_${id}${withTs ? '_ts' : ''}.txt`
  await downloadViaFetch(url, name)
}
const exportCsv = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  await downloadViaFetch(`/api/export/csv/${id}?spk=${store.showSpeakersInView && hasSpeakerLabels.value ? 1 : 0}`, `transcript_${id}.csv`)
}
const exportVtt = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  await downloadViaFetch(`/api/export/vtt/${id}`, `transcript_${id}.vtt`)
}
const exportSrt = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  await downloadViaFetch(store.getDownloadUrl(`outputs/${id}.srt`), `transcript_${id}.srt`)
}

// 고급 내보내기 모달
const showAdvanced = ref(false)
const sel = ref({ pdf: false, docx: false, txt: false, csv: false, srt: false, vtt: false })
const addTimestamps = ref(false)
const addSpeakers = ref(true)
const runAdvancedDownload = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  const tasks = []
  const prev = store.showSpeakersInView
  // 임시로 spk 옵션을 원하는 값에 맞춰 적용
  store.showSpeakersInView = !!addSpeakers.value
  if (sel.value.pdf) tasks.push(() => exportPdf(addTimestamps.value))
  if (sel.value.docx) tasks.push(() => exportDocx(addTimestamps.value))
  if (sel.value.txt) tasks.push(() => exportTxt(addTimestamps.value))
  if (sel.value.csv) tasks.push(() => exportCsv())
  if (sel.value.srt) tasks.push(() => exportSrt())
  if (sel.value.vtt) tasks.push(() => exportVtt())
  if (tasks.length === 0) {
    alert('내보낼 형식을 하나 이상 선택하세요')
    return
  }
  for (const t of tasks) {
    // 순차 실행 (브라우저 다운로드 정책 우회)
    // eslint-disable-next-line no-await-in-loop
    await t()
  }
  store.showSpeakersInView = prev
  showAdvanced.value = false
}

// 추가 상태/메서드 (두 번째 스크립트에서 병합)
const startEdit = ref(false)
const editText = ref('')
const showRename = ref(false)
const renameValue = ref('')
const showMove = ref(false)
const moveTarget = ref('uncategorized')

const openRename = () => {
  renameValue.value = currentItem.value?.filename || ''
  showRename.value = true
}
const confirmRename = () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  store.renameCurrentFile(id, renameValue.value.trim() || 'untitled')
  showRename.value = false
}
const openMove = () => {
  moveTarget.value = store.selectedCategoryId
  showMove.value = true
}
const confirmMove = () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  store.moveCurrentToCategory(id, moveTarget.value)
  showMove.value = false
}
const deleteCurrent = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  if (confirm('이 파일을 삭제할까요?')) {
    await store.deleteTranscription(id)
  }
}
const openEdit = async () => {
  const jobId = store.transcriptionResult?.job_id
  if (!jobId) return
  // SRT 세그먼트를 우선 사용하여 보기 좋은 줄바꿈으로 편집
  if (srtLoadedFor.value !== jobId || srtEntries.value.length === 0) {
    await loadSrt()
  }
  if (srtEntries.value.length) {
    editText.value = srtEntries.value.map(e => e.text).join('\n\n')
  } else {
    editText.value = store.transcriptionResult?.text || ''
  }
  // contenteditable 초기 콘텐츠 구성
  const lines = srtEntries.value.length ? srtEntries.value.map(e => e.text) : segmentedPlain.value
  const esc = (s) => s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
  editorHtml.value = lines.map(l => `<p>${esc(l)}</p>`).join('')
  startEdit.value = true
}
const saveEdit = async () => {
  const id = store.transcriptionResult?.job_id
  if (!id) return
  await store.saveEditedTranscript(id, editText.value)
  // 저장 후에는 로컬 상태만 갱신(히스토리/결과). 타임스탬프 모드는 필요 시 SRT를 새로 로드.
  srtEntries.value = []
  srtLoadedFor.value = null
  if (store.showTimestampsInView) await loadSrt()
  store.statusMessage = '편집 내용이 저장되었습니다'
  startEdit.value = false
}

// contenteditable 에디터 상태
const editorRef = ref(null)
const editorHtml = ref('')
const onEditorInput = () => {
  if (!editorRef.value) return
  // innerText는 <p> 단위를 줄바꿈으로 반환
  editText.value = editorRef.value.innerText.trimEnd()
}

// 공유 모달 상태/동작
const showShare = ref(false)
const copiedShare = ref(false)
const shareLink = computed(() => {
  const email = store.sharedByEmail || 'sgk1761451@gmail.com'
  try {
    const url = new URL(window.location.href)
    url.searchParams.set('shared', '1')
    url.searchParams.set('by', encodeURIComponent(email))
    return url.toString()
  } catch {
    const id = store.transcriptionResult?.job_id || ''
    const base = id ? `?job=${id}` : ''
    return `${base}${base ? '&' : '?'}shared=1&by=${encodeURIComponent(email)}`
  }
})
const copyShareLink = async () => {
  try {
    await navigator.clipboard.writeText(shareLink.value)
    copiedShare.value = true
    setTimeout(() => (copiedShare.value = false), 1500)
  } catch {}
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <!-- 본문 -->
    <div class="lg:col-span-3">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div v-if="store.sharedMode && store.sharedByEmail" class="mb-4">
          <div class="px-4 py-2 bg-gray-100 border border-gray-200 rounded-xl text-sm text-gray-700">
            <span class="mr-2">👤</span>{{ store.sharedByEmail }}이(가) 이 전사본을 공유했습니다.
          </div>
        </div>
        <header class="mb-6">
          <h2 class="text-3xl font-bold text-gray-800">{{ titleText }}</h2>
          <p v-if="createdAt" class="text-sm text-gray-500 mt-2">{{ createdAt }}</p>
        </header>

        <section>
          <!-- 인라인 편집 모드: 타임스탬프 토글과 무관하게 편집 가능 -->
          <div v-if="startEdit" class="space-y-3">
            <div ref="editorRef" contenteditable="true" class="min-h-[400px] leading-7 text-gray-800 focus:outline-none" v-html="editorHtml" @input="onEditorInput"></div>
            <div class="flex justify-end space-x-2">
              <button class="px-4 py-2 border rounded-lg" @click="startEdit = false">취소</button>
              <button class="px-4 py-2 bg-indigo-600 text-white rounded-lg" @click="saveEdit">저장</button>
            </div>
          </div>
          <!-- 타임스탬프 보기(ON) -->
          <div v-else-if="store.showTimestampsInView">
            <div v-if="srtLoading" class="text-sm text-gray-500">타임스탬프 로딩 중...</div>
            <div v-else-if="srtError" class="text-sm text-red-600">{{ srtError }}</div>
            <div v-else class="space-y-2 pr-2">
              <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
                <label class="inline-flex items-center space-x-2"><input type="checkbox" v-model="store.followPlayback" /><span>오디오 따라가기(자동 스크롤)</span></label>
                <label v-if="hasSpeakerLabels" class="inline-flex items-center space-x-2"><input type="checkbox" v-model="store.showSpeakersInView" /><span>화자 라벨 표시</span></label>
              </div>
              <div v-for="(e, idx) in srtEntries" :key="idx" :data-srt-idx="idx" class="flex items-start space-x-3 cursor-pointer group" @click="seekTo(idx)">
                <span v-if="e.start" class="select-none pointer-events-none text-xs px-2 py-0.5 rounded border"
                  :class="idx === activeIndex ? 'bg-indigo-600 text-white border-indigo-700' : 'bg-gray-100 text-gray-700 border-gray-200 group-hover:bg-gray-200'">{{ e.start }}</span>
                <span v-if="store.showSpeakersInView && e.speaker" class="select-none text-xs px-2 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200">화자 {{ e.speaker }}</span>
                <p class="leading-7" :class="idx === activeIndex ? 'text-indigo-700 font-medium' : 'text-gray-800'">{{ e.text }}</p>
              </div>
            </div>
          </div>
          <!-- 일반 보기(타임스탬프 OFF) -->
          <div v-else>
            <div v-if="srtEntries.length" class="space-y-2 pr-2">
              <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
                <label class="inline-flex items-center space-x-2"><input type="checkbox" v-model="store.followPlayback" /><span>오디오 따라가기(자동 스크롤)</span></label>
                <label v-if="hasSpeakerLabels" class="inline-flex items-center space-x-2"><input type="checkbox" v-model="store.showSpeakersInView" /><span>화자 라벨 표시</span></label>
              </div>
              <div v-for="(e, idx) in srtEntries" :key="idx" :data-srt-idx="idx" class="flex items-start space-x-2 leading-7 cursor-pointer" :class="idx === activeIndex ? 'text-indigo-700 font-medium' : 'text-gray-800'" @click="seekTo(idx)">
                <span v-if="store.showSpeakersInView && e.speaker" class="select-none text-xs px-2 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200">화자 {{ e.speaker }}</span>
                <span>{{ e.text }}</span>
              </div>
            </div>
            <div v-else class="space-y-2">
              <p v-for="(line, idx) in segmentedPlain" :key="idx" class="leading-7 text-gray-800">{{ line }}</p>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 오른쪽 사이드 (sticky 래퍼) -->
    <aside class="lg:col-span-1">
      <div class="space-y-6 lg:sticky lg:top-6">
        <div class="bg-white rounded-2xl shadow-xl p-4">
          <h3 class="text-sm font-bold text-gray-700 mb-3">내보내기</h3>
          <div class="space-y-2">
            <button class="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="exportPdf()">
              <span>📄</span>
              <span class="font-medium text-gray-800">PDF 다운로드</span>
            </button>
            <button class="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="exportDocx()">
              <span>📄</span>
              <span class="font-medium text-gray-800">DOCX 다운로드</span>
            </button>
            <button class="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="exportTxt()">
              <span>📝</span>
              <span class="font-medium text-gray-800">TXT 다운로드</span>
            </button>
            <button class="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="exportSrt()">
              <span>🧾</span>
              <span class="font-medium text-gray-800">SRT 다운로드</span>
            </button>
          </div>
          <div class="mt-4 p-3 bg-indigo-50 rounded-lg border border-indigo-100 cursor-pointer" @click="showAdvanced = true">
            <div class="flex items-center space-x-2 text-indigo-700 font-semibold">
              <span>⬇️</span>
              <span>고급 내보내기</span>
            </div>
            <div class="text-xs text-indigo-700/80">타임스탬프와 다양한 형식으로 내보내기</div>
          </div>
        </div>

        <div class="bg-white rounded-2xl shadow-xl p-4">
          <h3 class="text-sm font-bold text-gray-700 mb-3">더보기</h3>
          <!-- 공유 보기(축소 메뉴) -->
          <div v-if="store.sharedMode" class="space-y-2 text-sm">
            <label class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200 cursor-pointer">
              <span>타임스탬프 표시</span>
              <input type="checkbox" v-model="store.showTimestampsInView" />
            </label>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="showShare = true">
              <span>전사 공유</span>
              <span>🔗</span>
            </button>
            <a class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" :href="store.getAudioDownloadUrl(store.transcriptionResult?.job_id)" target="_blank">
              <span>오디오 다운로드</span>
              <span>🔊</span>
            </a>
          </div>
          <!-- 기본 보기(전체 메뉴) -->
          <div v-else class="space-y-2 text-sm">
            <label class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200 cursor-pointer">
              <span>타임스탬프 표시</span>
              <input type="checkbox" v-model="store.showTimestampsInView" />
            </label>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="showShare = true">
              <span>전사 공유</span>
              <span>🔗</span>
            </button>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="openEdit()">
              <span>전사 편집</span>
              <span>✏️</span>
            </button>
            <a class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" :href="store.getAudioDownloadUrl(store.transcriptionResult?.job_id)" target="_blank">
              <span>오디오 다운로드</span>
              <span>🔊</span>
            </a>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="openRename()">
              <span>파일 이름 변경</span>
              <span>📝</span>
            </button>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-gray-200" @click="openMove()">
              <span>이동</span>
              <span>📁</span>
            </button>
            <button class="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 border border-red-200 text-red-600" @click="deleteCurrent()">
              <span>파일 삭제</span>
              <span>🗑️</span>
            </button>
          </div>
        </div>
      </div>
    </aside>
  </div>

  <!-- 고급 내보내기 모달 -->
  <div v-if="showAdvanced" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="showAdvanced = false"></div>
    <div class="relative bg-white w-full max-w-sm rounded-2xl shadow-2xl p-6 mx-4">
      <div class="flex items-center justify-between mb-4">
        <h4 class="text-lg font-bold">1개의 전사 내보내기</h4>
        <button class="text-gray-500 hover:text-gray-700" @click="showAdvanced = false">✕</button>
      </div>
      <p class="text-sm text-gray-600 mb-4">하나 이상의 포맷을 선택하세요.</p>
      <div class="space-y-3">
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.pdf"/><span>PDF로 내보내기</span></label>
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.docx"/><span>DOCX로 내보내기</span></label>
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.txt"/><span>TXT로 내보내기</span></label>
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.csv"/><span>CSV로 내보내기</span></label>
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.srt"/><span>SRT로 내보내기</span></label>
        <label class="flex items-center space-x-3"><input type="checkbox" v-model="sel.vtt"/><span>VTT로 내보내기</span></label>
      </div>
      <div class="mt-5">
        <div class="font-semibold text-sm mb-2">설정</div>
        <label class="flex items-center space-x-3 text-sm"><input type="checkbox" v-model="addTimestamps"/><span>섹션 타임스탬프</span></label>
        <label v-if="hasSpeakerLabels" class="flex items-center space-x-3 text-sm"><input type="checkbox" v-model="addSpeakers"/><span>화자 라벨 포함</span></label>
        <p class="text-xs text-gray-500 mt-1">PDF, DOCX 및 TXT 형식의 각 섹션 앞에 라벨(예: [화자 1])을 추가합니다.</p>
      </div>
      <button class="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg" @click="runAdvancedDownload">다운로드</button>
    </div>
  </div>

  <!-- 이름 변경 모달 -->
  <div v-if="showRename" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="showRename = false"></div>
    <div class="relative bg-white w-full max-w-sm rounded-2xl shadow-2xl p-6 mx-4">
      <div class="flex items-center justify-between mb-4">
        <h4 class="text-lg font-bold">파일 이름 변경</h4>
        <button class="text-gray-500 hover:text-gray-700" @click="showRename = false">✕</button>
      </div>
      <input v-model="renameValue" class="w-full border rounded-lg px-3 py-2" />
      <div class="flex justify-end mt-4 space-x-2">
        <button class="px-4 py-2 border rounded-lg" @click="showRename = false">취소</button>
        <button class="px-4 py-2 bg-indigo-600 text-white rounded-lg" @click="confirmRename">변경</button>
      </div>
    </div>
  </div>

  <!-- 이동 모달 -->
  <div v-if="showMove" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="showMove = false"></div>
    <div class="relative bg-white w-full max-w-sm rounded-2xl shadow-2xl p-6 mx-4">
      <div class="flex items-center justify-between mb-4">
        <h4 class="text-lg font-bold">이동</h4>
        <button class="text-gray-500 hover:text-gray-700" @click="showMove = false">✕</button>
      </div>
      <select v-model="moveTarget" class="w-full border rounded-lg px-3 py-2">
        <option value="uncategorized">미분류</option>
        <option v-for="c in store.categories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <div class="flex justify-end mt-4 space-x-2">
        <button class="px-4 py-2 border rounded-lg" @click="showMove = false">취소</button>
        <button class="px-4 py-2 bg-indigo-600 text-white rounded-lg" @click="confirmMove">이동</button>
      </div>
    </div>
  </div>

  <!-- 전사 공유 모달 -->
  <div v-if="showShare" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="showShare = false"></div>
    <div class="relative bg-white w-full max-w-md rounded-2xl shadow-2xl p-6 mx-4">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center space-x-2">
          <span>🔗</span>
          <h4 class="text-lg font-bold">전사 공유</h4>
        </div>
        <button class="text-gray-500 hover:text-gray-700" @click="showShare = false">✕</button>
      </div>
      <p class="text-sm text-gray-600 mb-3">보안 링크를 복사해 공유하세요.</p>
      <input :value="shareLink" readonly class="w-full border rounded-lg px-3 py-2 mb-4 text-sm" />
      <button class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg" @click="copyShareLink">{{ copiedShare ? '복사됨!' : '보안 링크 복사' }}</button>
    </div>
  </div>
</template>