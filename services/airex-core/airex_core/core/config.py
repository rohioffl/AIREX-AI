"""Application configuration loaded from environment variables.

This module exposes a singleton ``settings`` object used across the backend.
Keep setting names stable because they are imported in multiple modules.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings. Loaded from environment / .env file."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/airex"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AIREX"

    # Security
    # SECRET_KEY must be set via environment variable in production
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_TO_A_SECURE_RANDOM_STRING"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 11520
    ALGORITHM: str = "HS256"

    # AI / LLM (LiteLLM + Vertex AI Gemini)
    LLM_PROVIDER: str = "vertex_ai"
    LLM_PRIMARY_MODEL: str = "vertex_ai/gemini-2.0-flash"
    LLM_FALLBACK_MODEL: str = "vertex_ai/gemini-2.0-flash-lite"
    LLM_LOCAL_TIMEOUT: int = 20
    LLM_FALLBACK_TIMEOUT: int = 30
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = 3
    LLM_CIRCUIT_BREAKER_COOLDOWN: int = 300
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_API_VERSION: str | None = None
    LLM_CORRELATION_HEADER: str = "X-Correlation-ID"
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-large"
    LLM_EMBEDDING_TIMEOUT: int = 15
    LLM_EMBEDDING_DIMENSION: int = 1024
    VERTEX_PROJECT: str = "smartops-automation"
    VERTEX_LOCATION: str = "us-central1"

    # Retrieval-Augmented Generation (RAG)
    RAG_RUNBOOK_LIMIT: int = 5
    RAG_INCIDENT_LIMIT: int = 3
    RAG_CONTEXT_MAX_CHARS: int = 4000
    RAG_QUERY_MAX_CHARS: int = 2000
    RAG_SNIPPET_MAX_CHARS: int = 600
    RAG_INCIDENT_SUMMARY_MAX_CHARS: int = 1600
    RAG_SIMILARITY_THRESHOLD: float = 0.7  # cosine distance; lower = more similar

    # Timeouts (seconds)
    INVESTIGATION_TIMEOUT: int = 60
    EXECUTION_TIMEOUT: int = 20
    VERIFICATION_TIMEOUT: int = 30
    LOCK_TTL: int = 120

    # Retry limits
    MAX_INVESTIGATION_RETRIES: int = 3
    MAX_EXECUTION_RETRIES: int = 3
    MAX_VERIFICATION_RETRIES: int = 3
    MAX_FALLBACK_ALTERNATIVES: int = (
        2  # max alternative actions to try after verification failure
    )

    # ── Auto-Approval Policy ────────────────────────────────────
    # Confidence threshold for auto-approval (0.0-1.0).
    # Actions with confidence >= threshold AND policy.auto_approve=True
    # skip human approval. Set to 1.0 to disable confidence-based auto-approval.
    AUTO_APPROVAL_CONFIDENCE_THRESHOLD: float = 0.85
    # Actions with risk_level=HIGH are never auto-approved regardless of confidence.
    AUTO_APPROVAL_BLOCK_HIGH_RISK: bool = True

    # ── Proactive Health Checks (Phase 6 ARE) ───────────────────
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL_MINUTES: int = 5
    HEALTH_CHECK_MAX_MONITORS: int = 200  # max Site24x7 monitors per run
    HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES: int = (
        30  # min gap between auto-incidents per target
    )

    # Webhook signature verification (empty = skip in dev)
    WEBHOOK_SECRET: str = ""

    # Google OAuth (leave empty to disable Google sign-in)
    GOOGLE_OAUTH_CLIENT_ID: str = ""

    # Multi-tenancy
    DEV_TENANT_ID: str = "00000000-0000-0000-0000-000000000000"

    # ── Cloud Provider Settings ──────────────────────────────────
    # GCP
    GCP_PROJECT_ID: str = ""
    GCP_ZONE: str = ""
    GCP_SERVICE_ACCOUNT_KEY: str = ""  # path to SA JSON key file (empty = use ADC)
    GCP_OS_LOGIN_USER: str = ""  # OS Login username (auto-resolved if empty)
    GCP_LOG_EXPLORER_ENABLED: bool = True

    # AWS
    AWS_REGION: str = "ap-south-1"
    AWS_PROFILE: str = ""  # empty = use instance role / default creds
    AWS_SSM_DOCUMENT: str = "AWS-RunShellScript"
    AWS_SSM_TIMEOUT: int = 30  # seconds to wait for SSM command

    # SSH fallback (when SSM / OS Login unavailable)
    SSH_KEY_PATH: str = ""  # path to private key
    SSH_USER: str = "ubuntu"
    SSH_PORT: int = 22
    SSH_TIMEOUT: int = 15

    # ── Site24x7 Monitoring API ──────────────────────────────────
    SITE24X7_ENABLED: bool = False
    SITE24X7_CLIENT_ID: str = ""
    SITE24X7_CLIENT_SECRET: str = ""
    SITE24X7_REFRESH_TOKEN: str = ""
    SITE24X7_BASE_URL: str = "https://www.site24x7.com/api"
    SITE24X7_ACCOUNTS_URL: str = "https://accounts.zoho.com"
    SITE24X7_TOKEN_CACHE_TTL: int = 3300  # seconds (55 min, tokens last 1hr)

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    FRONTEND_URL: str = "http://localhost:5173"  # For invitation links

    # Notifications
    SLACK_WEBHOOK_URL: str = ""
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 587
    EMAIL_SMTP_USER: str = ""
    EMAIL_SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
