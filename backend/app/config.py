from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis (Upstash)
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

    # Market Data
    TWELVE_DATA_API_KEY: str

    # AI
    ANTHROPIC_API_KEY: str

    # JWT Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # App
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Forex Intel"
    VERSION: str = "1.0.0"
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # Email Notifications
    RESEND_API_KEY: str = ""
    NOTIFICATION_EMAIL: str = ""
    

    # CORS - allowed origins for frontend
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://forex-intel-othmannchulas-projects.vercel.app",
        "https://forex-intel-mu.vercel.app",
    ]
    # Supported forex pairs
    SUPPORTED_PAIRS: List[str] = [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "USD/CHF",
        "AUD/USD",
        "USD/CAD",
        "XAU/USD",
    ]

    # Trading settings
    DEFAULT_RISK_PCT: float = 1.0
    MAX_DAILY_RISK_PCT: float = 3.0
    MIN_RR_RATIO: float = 1.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()