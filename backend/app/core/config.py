import os
from typing import List, Union
from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexus Core"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "supersecret_nexus_jwt_production_signing_key_9876543210"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql+asyncpg://nexus_user:nexus_password@nexus-db:5432/nexus_core_db"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.DATABASE_URL

    REDIS_URL: str = "redis://nexus-redis:6379/0"
    CELERY_BROKER_URL: str = "redis://nexus-redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://nexus-redis:6379/2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()