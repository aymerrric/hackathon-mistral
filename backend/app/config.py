"""Application settings, loaded from environment / .env via pydantic-settings.

Fully implemented — nothing to do here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://calltree:calltree@localhost:5432/calltree"
    mistral_api_key: str = ""
    mistral_chat_model: str = "mistral-large-latest"
    mistral_audio_model: str = "voxtral-mini-latest"
    media_dir: str = "./media"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
