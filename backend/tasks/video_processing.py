import ffmpeg


def extract_audio(video_path: str, output_audio_path: str):
    try:
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, output_audio_path, acodec="pcm_s16le", ac=1, ar="16000")
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True, output_audio_path
    except ffmpeg.Error as e:
        return False, f"오디오 추출 실패: {str(e)}"


def convert_wav_to_mp3(wav_path: str, mp3_path: str):
    try:
        # libmp3lame로 128k 스테레오 대신 1채널 유지, 샘플레이트 16k로 인코딩
        stream = ffmpeg.input(wav_path)
        stream = ffmpeg.output(
            stream,
            mp3_path,
            acodec="libmp3lame",
            audio_bitrate="128k",
            ac=1,
            ar="16000",
        )
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True, mp3_path
    except ffmpeg.Error as e:
        return False, f"MP3 변환 실패: {str(e)}"


def get_video_duration(video_path: str):
    try:
        probe = ffmpeg.probe(video_path)
        duration = float(probe["streams"][0]["duration"])
        return duration
    except Exception:
        return None