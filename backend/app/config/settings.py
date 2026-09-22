"""
Configuration module for ResilientRoute backend.
Loads from environment variables with sensible defaults.
No real secrets are stored here - all secrets come from .env.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    # LLM
    llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.deepseek.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_budget_cny: float = Field(default=50.0, alias="LLM_BUDGET_CNY")

    # External APIs
    hko_weather_api: str = Field(
        default="https://data.weather.gov.hk/weatherAPI/opendata/weather.php",
        alias="HKO_WEATHER_API",
    )
    mtr_schedule_api: str = Field(
        default="https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php",
        alias="MTR_SCHEDULE_API",
    )
    kmb_api_base: str = Field(
        default="https://data.etabus.gov.hk/v1/transport/kmb",
        alias="KMB_API_BASE",
    )

    # Database
    db_path: str = Field(default="backend/app/data/resilient.db", alias="DB_PATH")

    # Directories
    data_dir: str = Field(default="data", alias="DATA_DIR")
    graph_snapshot_dir: str = Field(
        default="backend/app/data/snapshots", alias="GRAPH_SNAPSHOT_DIR"
    )
    sim_result_dir: str = Field(default="data/sim", alias="SIM_RESULT_DIR")
    cache_dir: str = Field(default="backend/app/data/cache", alias="CACHE_DIR")

    # Offline mode
    offline_mode: bool = Field(default=False, alias="OFFLINE_MODE")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="backend/app/data/app.log", alias="LOG_FILE")

    # Deployment
    deploy_env: str = Field(default="local", alias="DEPLOY_ENV")
    deploy_version: str = Field(default="1.0.0-dev", alias="DEPLOY_VERSION")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def full_db_path(self) -> Path:
        return PROJECT_ROOT / self.db_path

    @property
    def full_data_dir(self) -> Path:
        return PROJECT_ROOT / self.data_dir

    @property
    def full_cache_dir(self) -> Path:
        return PROJECT_ROOT / self.cache_dir


settings = Settings()
