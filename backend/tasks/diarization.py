from typing import List, Dict, Any
import os
from dotenv import load_dotenv  # type: ignore

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend/
# 환경변수 로딩: .env → .env.local(존재 시 덮어쓰기)
try:
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    load_dotenv(os.path.join(BASE_DIR, ".env.local"), override=True)
except Exception:
    pass


def diarize_audio(audio_path: str) -> List[Dict[str, Any]]:
    """
    화자 분리 실행 (pyannote.audio 가용 시).
    설치가 없거나 실패하면 예외를 던져 호출부에서 안전하게 무시.
    반환 형식 예시: [{"start": 0.0, "end": 3.2, "speaker": "SPEAKER_1"}, ...]
    """
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception as e:
        raise e

    # Hugging Face 토큰 사용(필요 시)
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if token:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization", token=token)
    else:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
    # 기본: 파일 경로로 수행. 실패 시 파형 직접 주입으로 폴백.
    try:
        diarization = pipeline(audio_path)
    except Exception:
        try:
            import soundfile as sf  # type: ignore
            import torch  # type: ignore
            data, sr = sf.read(audio_path, dtype="float32", always_2d=True)
            waveform = torch.from_numpy(data.T)  # (channels, samples)
            diarization = pipeline({"waveform": waveform, "sample_rate": int(sr)})
        except Exception as e:
            raise e
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker": str(speaker),
        })
    return segments


def write_srt_with_speakers(whisper_segments: list, spk_segments: List[Dict[str, Any]], output_path: str) -> bool:
    """
    Whisper 세그먼트와 화자 세그먼트를 단순 매칭하여 SRT 작성.
    규칙: Whisper 세그먼트의 [start,end]에 가장 겹치는 화자 태그를 프리픽스.
    """
    # 내부 라벨 → 번호 매핑(등장 순서 기준). 최종 표기는 '화자 N'
    speaker_order: dict[str, int] = {}
    def get_index(label: str) -> int:
        base = str(label or "").strip()
        # 'SPEAKER_1' / 'SPEAKER 1' / '1' 형태 모두 정규화
        import re as _re
        m = _re.search(r"(\d+)$", base.replace("_", " "))
        key = base
        if m:
            key = f"SPEAKER_{int(m.group(1))}"
        if key not in speaker_order:
            speaker_order[key] = len(speaker_order) + 1
        return speaker_order[key]

    def pick_speaker(start: float, end: float) -> str:
        best = None
        best_overlap = 0.0
        for s in spk_segments:
            # 구간 겹침 길이
            ov = max(0.0, min(end, s["end"]) - max(start, s["start"]))
            if ov > best_overlap:
                best_overlap = ov
                best = s["speaker"]
        return best or "SPEAKER_1"

    def fmt_ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(whisper_segments, start=1):
                st = float(seg["start"])  # type: ignore
                ed = float(seg["end"])    # type: ignore
                text = str(seg.get("text", "")).strip()
                spk = pick_speaker(st, ed)
                idx = get_index(spk)
                f.write(f"{i}\n")
                f.write(f"{fmt_ts(st)} --> {fmt_ts(ed)}\n")
                f.write(f"[화자 {idx}] {text}\n\n")
        return True
    except Exception:
        return False


