import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
def _resolve_dir(env_key: str, default: Path) -> Path:
    val = os.getenv(env_key)
    if val:
        p = Path(val)
        return (BASE_DIR / p).resolve() if not p.is_absolute() else p.resolve()
    return default.resolve()

TEMP_DIR = _resolve_dir("TEMP_DIR", BASE_DIR / "temp")
DATA_DIR = _resolve_dir("DATA_DIR", BASE_DIR / "data")
USERS_DIR = DATA_DIR / "users"
LUTS_DIR  = DATA_DIR / "luts"
TEXTURES_DIR = DATA_DIR / "textures"

for d in (TEMP_DIR, DATA_DIR, USERS_DIR, LUTS_DIR, TEXTURES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Telegram ───────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── FFmpeg ─────────────────────────────────────────────────────────────────────
FFMPEG_PATH:  str = os.getenv("FFMPEG_PATH",  "ffmpeg")
FFPROBE_PATH: str = os.getenv("FFPROBE_PATH", "ffprobe")

# ── Processing limits ──────────────────────────────────────────────────────────
MAX_FILE_SIZE:       int  = int(os.getenv("MAX_FILE_SIZE", 2 * 1024**3))  # 2 GB
MAX_DURATION:        int  = int(os.getenv("MAX_DURATION", 0))              # 0 = unlimited
MAX_CONCURRENT_JOBS: int  = int(os.getenv("MAX_CONCURRENT_JOBS", 10))
RATE_LIMIT_PER_MIN:  int  = int(os.getenv("RATE_LIMIT_PER_MINUTE", 5))
USE_GPU:             bool = os.getenv("USE_GPU", "False").lower() == "true"

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Supported formats ──────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".flv", ".wmv", ".mpeg", ".mpg", ".3gp",
}
SUPPORTED_MIME_PREFIXES = ("video/",)
