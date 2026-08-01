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

    # 007-superadmin: conta única de plataforma, fora do modelo de tenant. Provisionada no boot
    # (idempotente) só se as duas vierem preenchidas — vazio nos ambientes onde não se aplica.
    superadmin_email: str = ""
    superadmin_password: str = ""
    superadmin_token_expire_minutes: int = 60

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

    # 009-integracao-portais: e-mail de contato exibido no Header do feed VRSync.
    canal_pro_feed_email: str = ""
    # SECRET_KEY única do sistema (não por tenant — a integração é homologada "por CRM" junto
    # ao Grupo OLX). Vazio até a homologação real acontecer; enquanto vazio, o webhook rejeita
    # tudo (nenhuma senha vazia é aceita).
    canal_pro_webhook_secret: str = ""

    # 009-integracao-portais: diretório onde as fotos de imóvel são gravadas (montado como
    # volume Docker em produção — sem dependência de storage externo, RNF009).
    uploads_dir: str = "uploads"


settings = Settings()
