from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Agenda Facturas Perú"
    app_url: str = "http://localhost:8000"
    secret_key: str = "cambia-esta-clave-secreta-desarrollo"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./agenda_facturas.db"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claim_email: str = "mailto:avisos@agenda-facturas.pe"
    cron_secret: str = ""
    sunat_api_token: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        url = (self.database_url or "").strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
