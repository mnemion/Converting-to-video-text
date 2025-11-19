from celery_app import celery_app
from tasks.video_processing import extract_audio, convert_wav_to_mp3
from tasks.transcription import TranscriptionService
from tasks.url_download import download_media_via_ytdlp
import os
import json


import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

transcription_service = TranscriptionService(model_size=os.getenv("WHISPER_MODEL_SIZE", "base"))


@celery_app.task(bind=True)
def transcribe_video_async(self, video_path: str, language: str = "ko", diarize: bool = False, model_size: str | None = None):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 10})

        audio_path = os.path.splitext(video_path)[0] + ".wav"
        success, result = extract_audio(video_path, audio_path)
        if not success:
            return {"success": False, "error": result}

        self.update_state(state="PROGRESS", meta={"progress": 30})

        # 요청 모델과 기본 모델 비교하여 인스턴스 선택
        env_default = os.getenv("WHISPER_MODEL_SIZE", "base").strip()
        use_model = (model_size or env_default).strip()
        svc = transcription_service if use_model == env_default else TranscriptionService(model_size=use_model)

        transcription_result = svc.transcribe(audio_path, language)
        if not transcription_result.get("success"):
            return {"success": False, "error": transcription_result.get("error", "전사 실패")}

        # (선택) 화자 분리: pyannote.audio 설치 여부에 따라 안전하게 건너뜀
        speakers = None
        if diarize:
            try:
                from tasks.diarization import diarize_audio
                speakers = diarize_audio(audio_path)
            except Exception:
                speakers = None

        self.update_state(state="PROGRESS", meta={"progress": 90})

        job_id = os.path.basename(video_path).split("_")[0]
        output_txt = os.path.join(OUTPUT_DIR, f"{job_id}.txt")
        output_srt = os.path.join(OUTPUT_DIR, f"{job_id}.srt")
        svc.save_transcription(transcription_result, output_txt)
        # 화자 분리가 있으면 SRT에 화자 태그를 프리픽스
        if speakers:
            try:
                from tasks.diarization import write_srt_with_speakers
                write_srt_with_speakers(transcription_result["segments"], speakers, output_srt)
            except Exception:
                svc.create_srt(transcription_result["segments"], output_srt)
        else:
            svc.create_srt(transcription_result["segments"], output_srt)

        # 메타 파일 보강: 업로드 시 저장이 실패한 경우 대비
        try:
            meta_path = os.path.join(OUTPUT_DIR, f"{job_id}.json")
            if not os.path.exists(meta_path):
                # video_path는 {job_id}_{original} 형태
                original_filename = os.path.basename(video_path).split("_", 1)[1] if "_" in os.path.basename(video_path) else os.path.basename(video_path)
                with open(meta_path, "w", encoding="utf-8") as mf:
                    json.dump({"job_id": job_id, "original_filename": original_filename}, mf, ensure_ascii=False)
        except Exception:
            pass

        # MP3 생성 (출력 폴더, 절대경로)
        try:
            mp3_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp3")
            ok, _ = convert_wav_to_mp3(audio_path, mp3_path)
        except Exception:
            mp3_path = None

        try:
            os.remove(video_path)
            os.remove(audio_path)
        except Exception:
            pass

        return {
            "success": True,
            "job_id": job_id,
            "text": transcription_result["text"],
            "txt_file": f"outputs/{job_id}.txt",
            "srt_file": f"outputs/{job_id}.srt",
            "audio_mp3": f"outputs/{job_id}.mp3" if mp3_path and os.path.exists(mp3_path) else None,
            "speakers": speakers,
            "diarize_requested": bool(diarize),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# URL 비동기 전사
@celery_app.task(bind=True)
def transcribe_url_async(self, url: str, job_id: str, language: str = "ko", diarize: bool = False, model_size: str | None = None):
    try:
        # 1) 다운로드 진행
        self.update_state(state="PROGRESS", meta={"progress": 5})
        ok, dl = download_media_via_ytdlp(url, job_id, UPLOAD_DIR)
        if not ok:
            return {"success": False, "error": dl.get("error", "다운로드 실패")}
        video_path = dl.get("path")
        original_title = str(dl.get("title") or os.path.basename(video_path))

        # 메타 보강
        try:
            meta_path = os.path.join(OUTPUT_DIR, f"{job_id}.json")
            payload = {"job_id": job_id, "original_filename": original_title, "source_url": url}
            if os.path.exists(meta_path):
                # 기존 메타와 병합
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        prev = json.load(mf)
                    prev.update(payload)
                    payload = prev
                except Exception:
                    pass
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(payload, mf, ensure_ascii=False)
        except Exception:
            pass

        # 2) 오디오 추출
        self.update_state(state="PROGRESS", meta={"progress": 15})
        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}.wav")
        success, result = extract_audio(video_path, audio_path)
        if not success:
            return {"success": False, "error": result}

        self.update_state(state="PROGRESS", meta={"progress": 30})

        # 3) 모델 선택 후 전사
        env_default = os.getenv("WHISPER_MODEL_SIZE", "base").strip()
        use_model = (model_size or env_default).strip()
        svc = transcription_service if use_model == env_default else TranscriptionService(model_size=use_model)
        transcription_result = svc.transcribe(audio_path, language)
        if not transcription_result.get("success"):
            return {"success": False, "error": transcription_result.get("error", "전사 실패")}

        # 4) 화자 분리(선택)
        speakers = None
        if diarize:
            try:
                from tasks.diarization import diarize_audio
                speakers = diarize_audio(audio_path)
            except Exception:
                speakers = None

        self.update_state(state="PROGRESS", meta={"progress": 90})

        # 5) 결과 저장
        output_txt = os.path.join(OUTPUT_DIR, f"{job_id}.txt")
        output_srt = os.path.join(OUTPUT_DIR, f"{job_id}.srt")
        svc.save_transcription(transcription_result, output_txt)
        if speakers:
            try:
                from tasks.diarization import write_srt_with_speakers
                write_srt_with_speakers(transcription_result["segments"], speakers, output_srt)
            except Exception:
                svc.create_srt(transcription_result["segments"], output_srt)
        else:
            svc.create_srt(transcription_result["segments"], output_srt)

        # 6) MP3 생성
        try:
            mp3_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp3")
            ok2, _ = convert_wav_to_mp3(audio_path, mp3_path)
        except Exception:
            mp3_path = None

        # 7) 정리
        try:
            os.remove(video_path)
            os.remove(audio_path)
        except Exception:
            pass

        return {
            "success": True,
            "job_id": job_id,
            "text": transcription_result["text"],
            "txt_file": f"outputs/{job_id}.txt",
            "srt_file": f"outputs/{job_id}.srt",
            "audio_mp3": f"outputs/{job_id}.mp3" if mp3_path and os.path.exists(mp3_path) else None,
            "speakers": speakers,
            "diarize_requested": bool(diarize),
            "original_filename": original_title,
            "source_url": url,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# URL 다운로드만 수행 (전사 X)
@celery_app.task(bind=True)
def download_url_async(self, url: str, job_id: str):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 5})

        def progress_cb(ratio: float, _info: dict):
            # 5% ~ 95% 사이로 매핑
            pct = 5 + int(max(0.0, min(1.0, ratio)) * 90)
            try:
                self.update_state(state="PROGRESS", meta={"progress": pct})
            except Exception:
                pass

        ok, dl = download_media_via_ytdlp(url, job_id, UPLOAD_DIR, progress_cb=progress_cb)
        if not ok:
            return {"success": False, "error": dl.get("error", "다운로드 실패")}
        video_path = dl.get("path")
        original_title = str(dl.get("title") or os.path.basename(video_path))

        # 메타 저장
        try:
            meta_path = os.path.join(OUTPUT_DIR, f"{job_id}.json")
            payload = {"job_id": job_id, "original_filename": original_title, "source_url": url}
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(payload, mf, ensure_ascii=False)
        except Exception:
            pass

        # 파일 크기
        try:
            size_bytes = os.path.getsize(video_path)
        except Exception:
            size_bytes = None

        self.update_state(state="PROGRESS", meta={"progress": 100})
        return {
            "success": True,
            "job_id": job_id,
            "video_path": video_path,
            "original_filename": original_title,
            "size_bytes": size_bytes,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

