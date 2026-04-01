"""Application configuration loaded from environment variables.

This module exposes a singleton ``settings`` object used across the backend.
Keep setting names stable because they are imported in multiple modules.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Application settings. Loaded from environment / .env file."""

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/airex?ssl=disable"
    )
    # Optional separate DB for platform_admins table (falls back to DATABASE_URL if empty)
    PLATFORM_ADMIN_DATABASE_URL: str = ""

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
    AUTH_RATE_LIMIT_REQUESTS: int = 20
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    APPROVAL_RATE_LIMIT_REQUESTS: int = 10
    APPROVAL_RATE_LIMIT_WINDOW_SECONDS: int = 60
    WEBHOOK_RATE_LIMIT_REQUESTS: int = 30
    WEBHOOK_RATE_LIMIT_WINDOW_SECONDS: int = 60

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
    LLM_EMBEDDING_MODEL: str = "text-embedding"
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

    # ── Internal Tool Server ────────────────────────────────────────
    INTERNAL_TOOL_TOKEN: str = ""

    # ── LangGraph Investigation ────────────────────────────────────
    USE_LANGGRAPH_INVESTIGATION: bool = True

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

    # ── Approval SLA (Phase 6 ARE) ───────────────────────────────
    # Maximum seconds to wait for operator approval before escalation
    APPROVAL_SLA_CRITICAL_SECONDS: int = 120   # 2 minutes
    APPROVAL_SLA_HIGH_SECONDS: int = 300        # 5 minutes
    APPROVAL_SLA_MEDIUM_SECONDS: int = 900      # 15 minutes
    APPROVAL_SLA_LOW_SECONDS: int = 1800        # 30 minutes

    # ── Confidence Validator (Phase 6 ARE) ───────────────────────
    # LLM confidence above which KG history is required (anti-hallucination)
    CONFIDENCE_VALIDATOR_THRESHOLD: float = 0.85
    # Minimum KG historical resolutions required for high-confidence actions
    CONFIDENCE_VALIDATOR_MIN_KG_HISTORY: int = 1

    # ── Reviewer Agent (Phase 6 ARE) ─────────────────────────────
    # Risk levels that trigger a second LLM reviewer call
    REVIEWER_AGENT_ENABLED: bool = True
    REVIEWER_AGENT_TIMEOUT: int = 20  # seconds

    # Webhook signature verification (empty = skip in dev)
    WEBHOOK_SECRET: str = ""

    # Google OAuth (leave empty to disable Google sign-in)
    GOOGLE_OAUTH_CLIENT_ID: str = ""

    # Multi-tenancy
    DEV_TENANT_ID: str = "00000000-0000-0000-0000-000000000000"

    # ── Tenant Credentials / AWS Secrets Manager ─────────────────
    # TTL for in-process secret cache (seconds); 0 disables caching
    TENANT_SECRET_CACHE_TTL_SECONDS: int = 60
    # Prefix used when constructing Secrets Manager paths for tenant/integration secrets
    AWS_SECRETS_PREFIX: str = "/airex/prod"

    # ── Cloud Provider Settings ──────────────────────────────────
    # GCP
    GCP_PROJECT_ID: str = ""
    GCP_ZONE: str = ""
    GCP_SERVICE_ACCOUNT_KEY: str = ""  # path to SA JSON key file (empty = use ADC)
    GCP_OS_LOGIN_USER: str = ""  # OS Login username (auto-resolved if empty)
    GCP_LOG_EXPLORER_ENABLED: bool = True

    # AWS
    AWS_REGION: str = "ap-south-1"
    AWS_SES_REGION: str = ""
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
    EMAIL_FROM: str = ""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT_ENV), ".env"),
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
