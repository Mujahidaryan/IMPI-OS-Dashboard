from enum import Enum
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegimeLabel(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    PANIC = "panic"
    UNKNOWN = "unknown"


class Settings(BaseSettings):
    # Pydantic Settings reads from environment and .env file.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Binance API Configuration
    BINANCE_API_KEY: str = "your_binance_api_key"
    BINANCE_API_SECRET: str = "your_binance_api_secret"

    # Exness MT5 Connection Configuration
    MT5_TERMINAL_PATH: str = "C:/Program Files/MetaTrader 5/terminal64.exe"
    MT5_LOGIN: int = 0
    MT5_PASSWORD: str = ""
    MT5_SERVER: str = "Exness-MT5Real7"

    # Infrastructure Services
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "postgresql://user:pass@host/dbname?sslmode=require"

    # Secondary / Fallback APIs
    ALPHA_VANTAGE_KEY: str = ""

    # Portfolio Risk Configurations
    ACCOUNT_BALANCE: float = 10000.0
    MAX_RISK_PCT: float = 1.0
    MAX_PORTFOLIO_HEAT: float = 5.0
    MAX_CORRELATED_EXPOSURE: float = 3.0

    # System Configuration
    LOG_LEVEL: str = "INFO"
    DASHBOARD_PORT: int = 3000
    API_PORT: int = 8000


@lru_cache()
def get_settings() -> Settings:
    return Settings()
