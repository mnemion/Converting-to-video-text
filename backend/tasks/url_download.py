import os
import re
from typing import Tuple, Dict, Any, Optional, Callable


def download_media_via_ytdlp(
    url: str,
    job_id: str,
    output_dir: str,
    progress_cb: Optional[Callable[[float, Dict[str, Any]], None]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """주어진 URL의 미디어를 yt-dlp로 다운로드한다.

    반환값: (성공여부, 결과/오류)
      - 성공 시 결과: {
          'path': 다운로드된 파일 절대경로,
          'title': 제목(가능한 경우),
          'ext': 확장자(점 제외),
        }
      - 실패 시 결과: {'error': '메시지'}
    """
    try:
        from yt_dlp import YoutubeDL  # type: ignore
    except Exception as e:
        return False, {"error": f"yt-dlp 미설치 또는 로드 실패: {e}"}

    os.makedirs(output_dir, exist_ok=True)

    # 환경 설정
    max_mb_env = os.getenv("YTDLP_MAX_MB")
    try:
        max_bytes = int(float(max_mb_env) * 1024 * 1024) if max_mb_env else None
    except Exception:
        max_bytes = None
    ytdlp_format = os.getenv("YTDLP_FORMAT", "bestaudio/best")
    socket_timeout = int(os.getenv("YTDLP_SOCKET_TIMEOUT", "30"))
    retries = int(os.getenv("YTDLP_RETRIES", "3"))
    proxy = os.getenv("YTDLP_PROXY")
    cookies = os.getenv("YTDLP_COOKIES_FILE")
    user_agent = os.getenv("YTDLP_USER_AGENT")

    # 제목이 없을 수 있으므로 파이프 폴백을 사용하고, 서식 지정자(s) 포함
    outtmpl = os.path.join(output_dir, f"{job_id}_%(title|id|epoch)s.%(ext)s")
    def _hook(d: Dict[str, Any]):
        if progress_cb is None:
            return
        try:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                ratio = float(downloaded) / float(total) if total else 0.0
                progress_cb(max(0.0, min(1.0, ratio)), d)
        except Exception:
            pass

    ydl_opts = {
        "format": ytdlp_format,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "restrictfilenames": True,
        "prefer_ffmpeg": True,
        "socket_timeout": socket_timeout,
        "retries": retries,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies and os.path.exists(cookies):
        ydl_opts["cookiefile"] = cookies
    if user_agent:
        ydl_opts["user_agent"] = user_agent

    try:
        # 1) 정보 추출 (선다운로드 없이)로 크기/제목 확인
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title")
            # 파일 크기 제한 검사 (가능한 경우)
            if max_bytes:
                sz = (
                    info.get("filesize")
                    or info.get("filesize_approx")
                    or (info.get("requested_formats") or [{}])[0].get("filesize")
                )
                if isinstance(sz, (int, float)) and sz > max_bytes:
                    return False, {"error": "파일이 너무 큽니다"}

        # 2) 실제 다운로드
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # 파일 경로 계산: 요청된 다운로드 목록 우선 사용
            filepath = None
            try:
                req = info.get("requested_downloads")
                if req and isinstance(req, list) and req[0].get("filepath"):
                    filepath = req[0]["filepath"]
            except Exception:
                filepath = None
            if not filepath:
                try:
                    # prepare_filename은 후처리 이전 파일명을 줄 수 있음
                    filepath = ydl.prepare_filename(info)
                except Exception:
                    filepath = None
            if not filepath or not os.path.exists(filepath):
                # outtmpl로 예상 파일명들 중 존재하는 것을 탐색
                title = info.get("title") or "download"
                # 확장자는 가변적이므로 폴더 내에서 job_id_ 로 시작하는 최신 파일 탐색
                candidates = [
                    os.path.join(output_dir, f) for f in os.listdir(output_dir)
                    if f.startswith(f"{job_id}_")
                ]
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                filepath = candidates[0] if candidates else None
                if not filepath or not os.path.exists(filepath):
                    return False, {"error": "다운로드된 파일을 찾을 수 없습니다"}
                ext = os.path.splitext(filepath)[1].lstrip(".")
                return True, {"path": filepath, "title": title, "ext": ext}

            ext = os.path.splitext(filepath)[1].lstrip(".")
            raw_title = info.get("title") or os.path.splitext(os.path.basename(filepath))[0]
            # 사용자 표시용 타이틀 정돈(공백 정리, 길이 제한)
            def normalize_title(t: str) -> str:
                t = re.sub(r"\s+", " ", str(t or "").strip())
                return t[:120] if len(t) > 120 else t
            title = normalize_title(raw_title)
            return True, {"path": filepath, "title": title, "ext": ext}
    except Exception as e:
        return False, {"error": str(e)}


