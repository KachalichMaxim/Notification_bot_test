"""Configuration loader from environment variables"""
import os
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""
    
    # Webhook settings
    WEBHOOK_URL = os.getenv(
        "WEBHOOK_URL", "http://bookntrack.online:8080/webhook_tasks"
    )
    PORT = int(os.getenv("PORT", "8080"))
    HOST = os.getenv("HOST", "0.0.0.0")
    
    # Telegram settings
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_API_URL = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    # Bitrix24 settings
    BITRIX24_DOMAIN = os.getenv("BITRIX24_DOMAIN", "")
    BITRIX24_AUTH_TOKEN = os.getenv(
        "BITRIX24_AUTH_TOKEN", "gu3ckdtubvwpbnru6418p8wbdv1khsqq"
    )

    # Task filtering settings
    # 2 = high, 3 = critical
    URGENT_PRIORITY_THRESHOLD = int(
        os.getenv("URGENT_PRIORITY_THRESHOLD", "2")
    )
    # Hours before deadline
    URGENT_DEADLINE_HOURS = int(os.getenv("URGENT_DEADLINE_HOURS", "24"))
    
    # Debug mode
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required in .env file")
        if not cls.BITRIX24_DOMAIN:
            print("Warning: BITRIX24_DOMAIN not set in .env file")

