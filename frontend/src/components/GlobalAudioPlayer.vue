<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useTranscriptionStore } from '../stores/transcription'

const store = useTranscriptionStore()

const jobId = computed(() => store.transcriptionResult?.job_id || null)
const currentItem = computed(() => jobId.value ? (store.history.find(h => h.id === jobId.value) || null) : null)
const title = computed(() => currentItem.value?.filename || '오디오')
const audioSrc = computed(() => jobId.value ? store.getDownloadUrl(`outputs/${jobId.value}.mp3`) : '')
const visible = computed(() => Boolean(jobId.value))

const audioRef = ref(null)
const bind = () => {
  const el = audioRef.value
  if (!el) return
  const onTime = () => store.reportAudioTime(el.currentTime || 0)
  const onPlay = () => store.reportAudioPlaying(true)
  const onPause = () => store.reportAudioPlaying(false)
  const onSeek = () => store.reportAudioTime(el.currentTime || 0)
  el.addEventListener('timeupdate', onTime)
  el.addEventListener('play', onPlay)
  el.addEventListener('pause', onPause)
  el.addEventListener('seeked', onSeek)
  el.__onTime = onTime
  el.__onPlay = onPlay
  el.__onPause = onPause
  el.__onSeek = onSeek
}
const unbind = () => {
  const el = audioRef.value
  if (!el) return
  try { el.removeEventListener('timeupdate', el.__onTime) } catch {}
  try { el.removeEventListener('play', el.__onPlay) } catch {}
  try { el.removeEventListener('pause', el.__onPause) } catch {}
  try { el.removeEventListener('seeked', el.__onSeek) } catch {}
  el.__onTime = null
  el.__onPlay = null
  el.__onPause = null
  el.__onSeek = null
}
onMounted(() => {
  bind()
  // 외부에서 시킹 요청 수신
  const onSeekCmd = (e) => {
    const t = e?.detail?.time
    const el = audioRef.value
    if (!el || typeof t !== 'number') return
    try { el.currentTime = Math.max(0, t) } catch {}
  }
  window.addEventListener('app-audio-seek', onSeekCmd)
  window.__onSeekCmd = onSeekCmd
})
onBeforeUnmount(() => {
  unbind()
  try { window.removeEventListener('app-audio-seek', window.__onSeekCmd) } catch {}
  window.__onSeekCmd = null
})
watch(audioSrc, () => { unbind(); setTimeout(bind, 0) })
</script>

<template>
  <div v-if="visible" class="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-gray-200 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]">
    <div class="max-w-7xl mx-auto px-4">
      <div class="flex items-center justify-between py-3">
        <div class="min-w-0 mr-4">
          <div class="text-sm font-medium text-gray-800 truncate">{{ title }}</div>
          <div class="text-xs text-gray-500 truncate">{{ jobId }}</div>
        </div>
        <audio ref="audioRef" :key="audioSrc" :src="audioSrc" controls preload="metadata" class="w-full max-w-3xl"></audio>
      </div>
    </div>
  </div>
  <!-- 공간 확보: 고정 플레이어 높이만큼 여유 (모바일 겹침 방지) -->
  <div v-if="visible" class="h-20"></div>
  
</template>


