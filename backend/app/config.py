from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://proptech:proptech@localhost:5432/proptech"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Fernet key (32 bytes urlsafe-base64) — gerar com `Fernet.generate_key()` em produção.
    encryption_key: str = "OT-EG2LO91jz5OWQ9y0zWXBk6f0K1UzLQeq7dK3s6xM="

    convite_expire_days: int = 7

    mercadopago_access_token: str = ""
    mercadopago_webhook_secret: str = ""
    dunning_dias_ate_suspender: int = 7

    platform_domain: str = "proptechavaliador.com.br"
    trial_days: int = 7

    # 006-dados-mercado: percentual abaixo do preço de mercado esperado para disparar o
    # alerta de imóvel subprecificado (RN2).
    subprecificado_threshold: float = 0.15

    sentry_dsn: str | None = None


settings = Settings()
