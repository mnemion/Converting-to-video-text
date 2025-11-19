import whisper
import os
try:
    import torch
except Exception:
    torch = None


class TranscriptionService:
    def __init__(self, model_size: str = "base"):
        env_model = os.getenv("WHISPER_MODEL_SIZE")
        selected_model_size = (env_model or model_size).strip()

        env_device = (os.getenv("WHISPER_DEVICE") or "").lower()
        if env_device in ("cpu", "cuda"):
            self.device = env_device
        else:
            self.device = "cuda" if (torch and hasattr(torch, "cuda") and torch.cuda.is_available()) else "cpu"

        print(f"Whisper 모델 로딩 중... ({selected_model_size}, device={self.device})")
        self.model = whisper.load_model(selected_model_size, device=self.device)
        # 전사 옵션 (환경변수 기반 튜닝)
        try:
            self.beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "3"))
        except Exception:
            self.beam_size = 3
        try:
            self.best_of = int(os.getenv("WHISPER_BEST_OF", "3"))
        except Exception:
            self.best_of = 3
        try:
            self.temperature = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
        except Exception:
            self.temperature = 0.0
        env_fp16 = os.getenv("WHISPER_FP16")
        if env_fp16 is None:
            self.fp16 = (self.device == "cuda")
        else:
            self.fp16 = env_fp16.lower() in ("1", "true", "yes")
        print("모델 로딩 완료!")

    def transcribe(self, audio_path: str, language: str = "ko"):
        # 언어 코드 정규화: ko, en, ja, zh, es, fr만 강제, 그 외/빈값은 자동 감지(None)
        allowed = {"ko", "en", "ja", "zh", "es", "fr"}
        lang = (language or "").lower().strip()
        lang_arg = lang if lang in allowed else None

        # 자동 감지 개선: 사전 감지 + 허용 언어에 한해 확률 임계치로 고정
        if lang_arg is None:
            try:
                audio = whisper.load_audio(audio_path)
                audio = whisper.pad_or_trim(audio)
                mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
                _, probs = self.model.detect_language(mel)
                # 허용 언어에 한해 최대 확률 선택
                best_lang = None
                best_prob = 0.0
                for k, p in probs.items():
                    if k in allowed and float(p) > best_prob:
                        best_lang, best_prob = k, float(p)
                # 임계치 (환경변수 조정 가능)
                threshold = float(os.getenv("WHISPER_LANG_THRESHOLD", "0.55"))
                if best_lang and best_prob >= threshold:
                    lang_arg = best_lang
            except Exception:
                pass
        try:
            result = self.model.transcribe(
                audio_path,
                language=lang_arg,  # None이면 Whisper 자동 감지
                task="transcribe",
                fp16=self.fp16,
                beam_size=self.beam_size,
                best_of=self.best_of,
                temperature=self.temperature,
                # 반복 억제/무음 처리 파라미터 (환경변수로 조절 가능)
                condition_on_previous_text=os.getenv("WHISPER_CONDITION_ON_PREV", "false").lower() in ("1", "true", "yes"),
                compression_ratio_threshold=float(os.getenv("WHISPER_COMPRESSION_RATIO", "2.4")),
                no_speech_threshold=float(os.getenv("WHISPER_NO_SPEECH", "0.6")),
                verbose=False,
            )
            return {
                "success": True,
                "text": result.get("text", ""),
                "segments": result.get("segments", []),
                "language": result.get("language", lang if lang_arg else "auto"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_transcription(self, result: dict, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.get("text", ""))
            return True
        except Exception as e:
            print(f"저장 실패: {e}")
            return False

    def create_srt(self, segments: list, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(segments, start=1):
                    start = self._format_timestamp(segment["start"])  # type: ignore
                    end = self._format_timestamp(segment["end"])      # type: ignore
                    text = str(segment.get("text", "")).strip()
                    f.write(f"{i}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
            return True
        except Exception as e:
            print(f"SRT 생성 실패: {e}")
            return False

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"