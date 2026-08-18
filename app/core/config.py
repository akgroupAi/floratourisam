"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Medical Tourism Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # JWT Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24
    # Admin-created accounts get a longer window to set their first password
    DOCTOR_INVITE_TOKEN_EXPIRE_HOURS: int = 72

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://floramedcare.com",
        "https://www.floramedcare.com"
    ]
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            if v.startswith("["):
                import json

                return json.loads(v)
            return [origin.strip() for origin in v.split(",")]
        return v

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Super Admin
    FIRST_SUPERUSER_EMAIL: str = "admin@medicaltourism.com"
    FIRST_SUPERUSER_PASSWORD: str = "Admin@123456"

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"

    # External Services
    PAYMENT_GATEWAY_KEY: Optional[str] = None
    PAYMENT_GATEWAY_SECRET: Optional[str] = None

    # Razorpay (Only Payment Gateway)
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_CURRENCY: str = "USD"

    # Platform fee charged to the customer on top of a booking subtotal, as a
    # percentage. Set to 0 to disable. Applies to every payable booking.
    PLATFORM_FEE_PERCENT: float = 5.0

    # Cancellation policy. Cancel at least FREE_WINDOW_HOURS before the booking starts
    # and the customer is refunded, less CHARGE_PERCENT. Inside that window, nothing is
    # refunded. The platform fee is retained either way unless made refundable.
    CANCELLATION_FREE_WINDOW_HOURS: int = 48
    CANCELLATION_CHARGE_PERCENT: float = 10.0
    PLATFORM_FEE_REFUNDABLE: bool = False

    # AI / RAG Chatbot
    AI_SERVICE_URL: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_TOP_K: int = 8
    RAG_SIMILARITY_THRESHOLD: float = 0.3
    # Below this best-match score a question is treated as off-topic and the
    # assistant redirects instead of answering from general world knowledge.
    RAG_SCOPE_THRESHOLD: float = 0.15

    # SMTP Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = "noreply@medicaltourism.com"
    EMAIL_FROM_NAME: str = "Medical Tourism Platform"

    # Frontend URL (used to build verification / reset links in emails)
    FRONTEND_URL: str = "https://floramedcare.com"

    # Google Calendar / Meet
    GOOGLE_CALENDAR_ENABLED: bool = False
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None  # Path to service account JSON file
    GOOGLE_CALENDAR_TIMEZONE: str = "UTC"

    # JaaS (Jitsi as a Service, 8x8.vc) — hosted Jitsi with JWT auth.
    # Both patient and doctor are signed in as moderator, so neither one
    # hits the "waiting for the host" screen that public meet.jit.si shows
    # to anonymous joiners. Used as the fallback when Google Calendar is
    # disabled; takes priority over the plain meet.jit.si fallback below.
    JAAS_ENABLED: bool = False
    JAAS_APP_ID: Optional[str] = None
    JAAS_API_KEY_ID: Optional[str] = None  # "kid" from the JaaS API key
    JAAS_PRIVATE_KEY_PATH: Optional[str] = None  # path to the downloaded .pk / .pem file
    JAAS_DOMAIN: str = "8x8.vc"

    # Daily.co — hosted WebRTC rooms via REST API. Rooms are private
    # (token-gated) with knocking disabled, and both patient and doctor get
    # an owner-level meeting token, so whoever joins first just starts the
    # call — no shared email domain or per-doctor account needed. Checked
    # before Google Calendar / JaaS when picking a video provider.
    DAILY_ENABLED: bool = False
    DAILY_API_KEY: Optional[str] = None
    DAILY_DOMAIN: Optional[str] = None  # your Daily subdomain, e.g. "floramedcare" -> floramedcare.daily.co
    DAILY_API_BASE_URL: str = "https://api.daily.co/v1"

    # Self-hosted Jitsi Meet (open source, e.g. docker-jitsi-meet) with JWT
    # auth. Same moderator-JWT trick as JaaS, but pointed at a Jitsi server
    # you deploy and control — no per-minute SaaS cost, but you own the
    # hosting, TURN/STUN, and TLS. JITSI_SELFHOSTED_APP_ID/APP_SECRET must
    # match the JWT_APP_ID / JWT_APP_SECRET configured on that server.
    JITSI_SELFHOSTED_ENABLED: bool = False
    JITSI_SELFHOSTED_DOMAIN: Optional[str] = None  # host (and :port if non-standard), e.g. "meet.floramedcare.com" or "147.93.104.58:18443"
    JITSI_SELFHOSTED_BASE_PATH: Optional[str] = None  # subdir prefix for multi-tenant deployments, e.g. "DistantRepresentationsMarkForth" — omit if your instance serves from "/"
    JITSI_SELFHOSTED_APP_ID: str = "floramedcare"
    JITSI_SELFHOSTED_APP_SECRET: Optional[str] = None

    @property
    def async_database_url(self) -> str:
        """Return async database URL."""
        return self.DATABASE_URL

    @property
    def sync_database_url(self) -> str:
        """Return sync database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
