import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _safe_int(name: str, default: int, min_val: int = 1) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return max(min_val, v)
    except (ValueError, TypeError):
        return default


ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
SCRAPING_TIMEOUT       = _safe_int("SCRAPING_TIMEOUT", 10)
MAX_CONCURRENT_LEADS   = _safe_int("MAX_CONCURRENT_LEADS", 10)
MAX_CONCURRENT_IA      = _safe_int("MAX_CONCURRENT_IA", 3)
# Cortes alinhados ao ICP oficial da Eden (skill analise-leads-eden): 75/55/35
SCORE_THRESHOLD_MORNO  = _safe_int("SCORE_THRESHOLD_MORNO", 55, min_val=0)
SCORE_THRESHOLD_QUENTE = _safe_int("SCORE_THRESHOLD_QUENTE", 75, min_val=0)
DB_PATH                = BASE_DIR / "leads.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
