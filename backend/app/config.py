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

    # --- Voice agent (web mic + Twilio phone) ------------------------------
    # Realtime STT over WebSocket (Voxtral Transcribe 2 realtime).
    mistral_realtime_model: str = "voxtral-mini-transcribe-realtime-2602"
    # How far transcription may lag the audio; lower = snappier turn taking.
    # Must be a multiple of 80 in [80, 1200].
    voice_streaming_delay_ms: int = 480
    # Silence (no new transcript deltas) after which a caller turn is final.
    voice_turn_silence_ms: int = 900
    # TTS (Voxtral TTS). Voice is resolved by preset name via the Voices API.
    mistral_tts_model: str = "voxtral-mini-tts-2603"
    mistral_tts_voice: str = "Jane - Neutral"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
