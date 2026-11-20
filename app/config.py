"""Configuration is read at runtime; secrets are never returned to the browser."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv('WFS_DATA_DIR', str(ROOT / 'data'))).resolve()
PROJECTS = DATA / 'projects'
DB = DATA / 'wfs.sqlite3'
STATIC = ROOT / 'app' / 'static'
MAX_TASKS = max(1, min(16, int(os.getenv('WFS_MAX_TASKS', '8'))))
MAX_CALLS = max(3, min(70, int(os.getenv('WFS_MAX_MODEL_CALLS', '24'))))
MAX_TOKENS = max(10000, min(2000000, int(os.getenv('WFS_MAX_TOTAL_TOKENS', '300000'))))
MAX_PARALLEL = max(1, min(4, int(os.getenv('WFS_MAX_PARALLEL', '2'))))
MAX_ACTIVE_PROJECTS = max(1, min(8, int(os.getenv('WFS_MAX_ACTIVE_PROJECTS', '3'))))
MAX_ESTIMATED_COST_USD = max(0.0, float(os.getenv('WFS_MAX_ESTIMATED_COST_USD', '0')))
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
API_BASE = os.getenv('WFS_PROVIDER_URL', 'https://api.openai.com/v1/responses')
SESSION_KEY = os.getenv('WFS_SESSION_SECRET', '')
PASSWORD_HASH = os.getenv('WFS_ADMIN_PASSWORD_HASH', '')
COOKIE_SECURE = os.getenv('WFS_COOKIE_SECURE', 'false').lower() == 'true'
AUTH_TTL_SECONDS = 8 * 3600
MAX_PROJECT_FILES = 70
MAX_PROJECT_BYTES = 1_500_000


def configured():
    return bool(SESSION_KEY and PASSWORD_HASH)


def ai_enabled():
    return bool(os.getenv('OPENAI_API_KEY', '').strip())

TASK_REVIEW_TIMEOUT_SECONDS = int(os.getenv('WFS_TASK_REVIEW_TIMEOUT_SECONDS','86400'))
