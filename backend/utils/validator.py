import os


ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "flv", "wmv"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_size(file_obj) -> bool:
    try:
        current = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(current)
        return size <= MAX_FILE_SIZE
    except Exception:
        return True


