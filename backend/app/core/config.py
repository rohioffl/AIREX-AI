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
    VERTEX_PROJECT: str = "smartops-automation"
    VERTEX_LOCATION: str = "us-central1"

    # Timeouts (seconds)
    INVESTIGATION_TIMEOUT: int = 60
    EXECUTION_TIMEOUT: int = 20
    VERIFICATION_TIMEOUT: int = 30
    LOCK_TTL: int = 120

    # Retry limits
    MAX_INVESTIGATION_RETRIES: int = 3
    MAX_EXECUTION_RETRIES: int = 3
    MAX_VERIFICATION_RETRIES: int = 3

    # Webhook signature verification (empty = skip in dev)
    WEBHOOK_SECRET: str = ""

    # Multi-tenancy
    DEV_TENANT_ID: str = "00000000-0000-0000-0000-000000000000"

    # ── Cloud Provider Settings ──────────────────────────────────
    # GCP
    GCP_PROJECT_ID: str = ""
    GCP_ZONE: str = ""
    GCP_SERVICE_ACCOUNT_KEY: str = ""       # path to SA JSON key file (empty = use ADC)
    GCP_OS_LOGIN_USER: str = ""             # OS Login username (auto-resolved if empty)
    GCP_LOG_EXPLORER_ENABLED: bool = True

    # AWS
    AWS_REGION: str = "ap-south-1"
    AWS_PROFILE: str = ""                   # empty = use instance role / default creds
    AWS_SSM_DOCUMENT: str = "AWS-RunShellScript"
    AWS_SSM_TIMEOUT: int = 30               # seconds to wait for SSM command

    # SSH fallback (when SSM / OS Login unavailable)
    SSH_KEY_PATH: str = ""                  # path to private key
    SSH_USER: str = "ubuntu"
    SSH_PORT: int = 22
    SSH_TIMEOUT: int = 15

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
