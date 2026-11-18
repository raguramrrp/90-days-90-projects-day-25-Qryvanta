from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "QRYVANTA"
    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'qryvanta.db').as_posix()}"

    JWT_SECRET_KEY: str = "change-this-development-secret-key-before-deployment-qryvanta-32bytes"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    UPLOAD_DIR: str = str(PROJECT_ROOT / "backend" / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".csv", ".json", ".log", ".docx", ".xlsx"
    ]

    HIGH_CONFIDENCE_THRESHOLD: float = 0.80
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.55
    SIMILARITY_THRESHOLD: float = 0.25

    ML_MODELS_DIR: str = str(PROJECT_ROOT / "ml" / "models")
    SYNTHETIC_DATA_DIR: str = str(PROJECT_ROOT / "data" / "synthetic")

    @property
    def resolved_database_url(self) -> str:
        """Resolve relative SQLite paths against PROJECT_ROOT so CWD never splits databases."""
        url = self.DATABASE_URL.strip()
        if url.startswith("sqlite:///./"):
            rel_path = url[len("sqlite:///./"):]
            return f"sqlite:///{(PROJECT_ROOT / rel_path).resolve().as_posix()}"
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////") and ":" not in url[len("sqlite:///"):len("sqlite:///")+3]:
            rel_path = url[len("sqlite:///"):]
            return f"sqlite:///{(PROJECT_ROOT / rel_path).resolve().as_posix()}"
        return url

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
