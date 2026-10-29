import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    APP_NAME: str = "Nesta Deal Hunter Szczecin"
    APP_VERSION: str = "4.16.0"  # SSOT Wersji (Sekcja 3.3)
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    @property
    def is_dev_env(self) -> bool:
        return self.TRACKER_ENV == "DEV"

    # Baza Danych SQLite WAL
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/deals.db")

    # AI (Google Gemini)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Alerty Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Integracja z Nesta Master Tracker
    TRACKER_PROD_URL: str = os.getenv("TRACKER_PROD_URL", "http://srv75.mikr.us:20120/api/staging")
    TRACKER_DEV_URL: str = os.getenv("TRACKER_DEV_URL", "http://srv75.mikr.us:30120/api/staging")
    TRACKER_ENV: str = os.getenv("TRACKER_ENV", "DEV").upper()

    @property
    def tracker_active_url(self) -> str:
        return self.TRACKER_PROD_URL if self.TRACKER_ENV == "PROD" else self.TRACKER_DEV_URL

    # IMAP (Powiadomienia mailowe z OLX / Otodom)
    IMAP_HOST: str = os.getenv("IMAP_HOST", "")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER: str = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    IMAP_FOLDER: str = os.getenv("IMAP_FOLDER", "INBOX")

    # Kryteria inwestycyjne Nesta Home Szczecin
    DEFAULT_MIN_ROI: float = float(os.getenv("DEFAULT_MIN_ROI", "0.16"))
    MIN_NET_PROFIT_PLN: float = float(os.getenv("MIN_NET_PROFIT_PLN", "30000.0"))
    SWEET_SPOT_MIN_M2: float = 38.0
    SWEET_SPOT_MAX_M2: float = 55.0
    QUICK_FLIP_MIN_M2: float = 25.0
    QUICK_FLIP_MAX_M2: float = 35.0
    LARGE_FLIP_MAX_M2: float = 70.0

settings = Settings()
