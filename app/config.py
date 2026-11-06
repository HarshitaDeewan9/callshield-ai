from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", validate_assignment=True)
    app_env: Literal["development", "production"] = "development"
    app_api_key: SecretStr = SecretStr("")
    mock_mode: bool = True
    gnani_api_key: SecretStr = SecretStr("")
    prisma_enabled: bool = True
    timbre_enabled: bool = True
    timbre_model: Literal["timbre-v2.5"] = "timbre-v2.5"
    evon_base_url: str = "http://127.0.0.1:8080/v1"
    evon_api_key: SecretStr = SecretStr("")
    evon_model: str = "evon"
    evon_timeout_seconds: float = Field(120, gt=0)
    # Environment values arrive as strings; parse as int before enforcing the single-slot limit.
    evon_max_concurrent: int = Field(1, ge=1, le=1)
    evon_queue_size: int = Field(4, ge=0, le=100)
    evon_queue_timeout_seconds: float = Field(5, gt=0)
    evon_context_tokens: int = Field(512, ge=256)
    translation_provider: Literal["identity", "google"] = "identity"
    translate_hindi: bool = False
    google_cloud_project: str = ""
    provider_timeout_seconds: float = Field(60, gt=0)
    max_audio_mb: int = Field(15, ge=1, le=50)
    max_audio_seconds: float = Field(60, gt=0, le=60)
    max_transcript_chars: int = Field(3000, ge=1)
    report_ttl_seconds: float = Field(1800, gt=0)
    warning_audio_ttl_seconds: float = Field(3600, gt=0)
    max_reports: int = Field(500, ge=1)
    max_cached_audio_mb: int = Field(32, ge=10, le=512)
    requests_per_minute: int = Field(60, ge=1)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    live_enabled: bool = True
    live_max_sessions: int = Field(10, ge=1, le=100)
    live_session_seconds: float = Field(900, gt=0, le=3600)
    live_max_turns: int = Field(200, ge=1, le=1000)
    live_history_size: int = Field(100, ge=1, le=500)
    live_checkpoint_seconds: float = Field(1, ge=0.1, le=60)
    live_stt_max_speech_seconds: float = Field(5, ge=5, le=30)
    live_event_queue_size: int = Field(64, ge=4, le=256)
    risk_max_tokens: int = Field(256, ge=128, le=512)

    @model_validator(mode="after")
    def secure_production(self):
        key = self.app_api_key.get_secret_value()
        if (self.app_env == "production" or not self.mock_mode) and len(key) < 24:
            raise ValueError(
                "Set APP_API_KEY to a secret with at least 24 characters for real/production mode"
            )
        return self
