from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}")
ADMIN_ACCOUNT = os.getenv('ADMIN_ACCOUNT', os.getenv('ADMIN_EMAIL', '传统村落后台管理'))
ADMIN_EMAIL = ADMIN_ACCOUNT
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'SX666')
ADMIN_NAME = os.getenv('ADMIN_NAME', '传统村落后台管理')
SESSION_DAYS = int(os.getenv('SESSION_DAYS', '7'))
PROCESSED_VILLAGES = DATA_DIR / 'processed' / 'shanxi_villages.json'
CORS_ORIGINS = [x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000').split(',') if x.strip()]

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '').strip()
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/')
DEEPSEEK_CHAT_MODEL = os.getenv('DEEPSEEK_CHAT_MODEL', 'deepseek-chat')
DEEPSEEK_REASONER_MODEL = os.getenv('DEEPSEEK_REASONER_MODEL', 'deepseek-reasoner')
AI_REQUEST_TIMEOUT = float(os.getenv('AI_REQUEST_TIMEOUT', '75'))
AI_MAX_OUTPUT_TOKENS = int(os.getenv('AI_MAX_OUTPUT_TOKENS', '2200'))
AI_WEB_SEARCH_ENABLED = os.getenv('AI_WEB_SEARCH_ENABLED', '1').lower() not in {'0', 'false', 'no'}
WEB_SEARCH_TIMEOUT = float(os.getenv('WEB_SEARCH_TIMEOUT', '18'))
WEB_SEARCH_ALLOWED_DOMAINS = tuple(
    x.strip().lower() for x in os.getenv(
        'WEB_SEARCH_ALLOWED_DOMAINS',
        'gov.cn,dmctv.cn,ncha.gov.cn,mct.gov.cn,xinhuanet.com,people.com.cn,shaanxi.gov.cn,whhlyt.shaanxi.gov.cn,cnwest.com'
    ).split(',') if x.strip()
)

TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '').strip()

UPLOAD_DIR = DATA_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_MB', '8')) * 1024 * 1024
MAX_IMAGE_EDGE = int(os.getenv('MAX_IMAGE_EDGE', '2600'))

SMTP_HOST = os.getenv('SMTP_HOST', '').strip()
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '').strip()
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER).strip()
FEEDBACK_TO = os.getenv('FEEDBACK_TO', '').strip()
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', '1').lower() not in {'0', 'false', 'no'}
