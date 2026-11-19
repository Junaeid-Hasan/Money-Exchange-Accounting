from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Foreign Currency Exchange & Accounting System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "money-exchange-secret-key-production-ready-secure-random"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite:///./money_exchange.db"

    # Currency Configuration
    BASE_CURRENCY: str = "BDT"
    PRIMARY_FOREIGN_CURRENCY: str = "MYR"
    TIMEZONE: str = "Asia/Dhaka"

    # Decimal Precisions
    CURRENCY_DECIMAL_PLACES: int = 2
    RATE_DECIMAL_PLACES: int = 4
    QUANTITY_DECIMAL_PLACES: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
