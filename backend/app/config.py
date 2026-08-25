from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Provider presets: any OpenAI-compatible chat endpoint works.
_LLM_PRESETS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:3b",  # fast local instruct model
        "api_key": "ollama",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "search_model": "groq/compound",  # agentic model with built-in web search
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "IN-GRES AI"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql+psycopg://ingres:ingres@localhost:5432/ingres"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Signed arithmetic CAPTCHA on public signup (see app/core/captcha.py)
    REGISTRATION_CAPTCHA_ENABLED: bool = True

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    REDIS_URL: str = "redis://localhost:6379/0"

    ENABLE_GEOMETRY: bool = True
    AUTO_CREATE_SCHEMA: bool = False

    # AI / LLM — any OpenAI-compatible endpoint. Pick a provider preset with
    # LLM_PROVIDER (ollama | groq | openai | gemini | mistral) and optionally
    # override LLM_BASE_URL / LLM_MODEL for full control.
    #   Groq  (fastest cloud, free tier): https://api.groq.com/openai/v1
    #   Ollama (local, no key):          http://localhost:11434/v1
    LLM_ENABLED: bool = False
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = ""  # blank -> derived from LLM_PROVIDER
    LLM_API_KEY: str = ""  # blank is fine for local Ollama
    LLM_MODEL: str = ""  # blank -> per-provider default (see below)
    # Model used when the assistant must search the internet itself
    # (blank -> per-provider default, e.g. groq/compound on Groq).
    LLM_SEARCH_MODEL: str = ""
    # Full LLM control: the model composes EVERY chat reply (dataset facts are
    # still computed locally and injected as authoritative context, so numbers
    # stay grounded). False = hybrid mode (templates for data, LLM for the rest).
    LLM_FULL_CONTROL: bool = False
    LLM_TIMEOUT_SECONDS: int = 90

    # Web search fallback (keyless DuckDuckGo via ddgs). When the knowledge
    # base has nothing relevant, the assistant searches the internet and cites
    # the sources it used.
    WEB_SEARCH_ENABLED: bool = True
    WEB_SEARCH_MAX_RESULTS: int = 4
    WEB_SEARCH_TIMEOUT_SECONDS: int = 8

    def resolved_llm_base_url(self) -> str:
        return self.llm_backend_chain()[0]["base_url"]

    def resolved_llm_model(self) -> str:
        return self.llm_backend_chain()[0]["model"]

    def resolved_llm_api_key(self) -> str:
        return self.llm_backend_chain()[0].get("api_key", "")

    def resolved_llm_search_model(self) -> str:
        """Model with built-in internet search (e.g. groq/compound)."""
        preset = _LLM_PRESETS.get(self.LLM_PROVIDER.lower().strip(), {})
        return self.LLM_SEARCH_MODEL.strip() or preset.get("search_model", "")

    def llm_search_backend(self) -> dict[str, str] | None:
        """Backend able to search the web itself, or None when unavailable."""
        if not self.resolved_llm_search_model():
            return None
        for backend in self.llm_backend_chain():
            if backend["provider"] == self.LLM_PROVIDER.lower().strip():
                return {**backend, "model": self.resolved_llm_search_model()}
        return None

    def llm_backend_chain(self) -> list[dict[str, str]]:
        """Ordered OpenAI-compatible backends to try for LLM calls.

        First entry: the configured provider (preset or explicit overrides).
        Then, for any non-Ollama provider, local Ollama as a keyless fallback
        so the assistant keeps working offline / before an API key is added.
        """
        provider = self.LLM_PROVIDER.lower().strip() or "ollama"
        preset = _LLM_PRESETS.get(provider, {})
        entries: list[dict[str, str]] = []
        base = self.LLM_BASE_URL.strip() or preset.get("base_url", "")
        if base:
            entries.append(
                {
                    "provider": provider,
                    "base_url": base.rstrip("/"),
                    "model": self.LLM_MODEL.strip()
                    or preset.get("model", "qwen2.5:3b"),
                    "api_key": self.LLM_API_KEY.strip() or preset.get("api_key", ""),
                }
            )
        if provider != "ollama":
            local = _LLM_PRESETS["ollama"]
            entries.append(
                {
                    "provider": "ollama",
                    "base_url": local["base_url"],
                    "model": self.LLM_MODEL.strip() or local["model"],
                    "api_key": local["api_key"],
                }
            )
        if not entries:  # unknown provider with no usable URL -> local Ollama
            local = _LLM_PRESETS["ollama"]
            entries.append(dict(local, provider="ollama"))
        return entries

    # RAG / embeddings
    KNOWLEDGE_DIR: str = "knowledge/documents"
    RAG_MODE: str = "hybrid"  # bm25 | vector | hybrid
    EMBEDDING_ENABLED: bool = False
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIM: int = 384
    EMBEDDING_TIMEOUT_SECONDS: int = 30

    # Chat memory
    CHAT_MEMORY_TURNS: int = 8

    # Alerts / notifications
    NOTIFICATIONS_ENABLED: bool = True
    ALERT_CHECK_ON_IMPORT: bool = True
    EMAIL_NOTIFICATIONS_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@ingres.in"
    SMTP_USE_TLS: bool = True

    # Scheduled reports / digests. When enabled, a background loop processes
    # due ReportSchedule rows every SCHEDULED_REPORTS_CHECK_MINUTES, renders
    # the assessment PDF and emails it to the recipients (SMTP required for
    # delivery; PDFs are always stored under DATA_DIR/SCHEDULED_REPORTS_DIR).
    SCHEDULED_REPORTS_ENABLED: bool = False
    SCHEDULED_REPORTS_CHECK_MINUTES: int = 60
    SCHEDULED_REPORTS_DIR: str = "scheduled_reports"

    # Data-quality anomaly scanning. The scan is also runnable on demand from
    # the admin console; QUALITY_SCAN_ON_BOOT additionally runs it once when
    # the app starts.
    QUALITY_SCAN_ON_BOOT: bool = False
    QUALITY_MAX_FLAGS_PER_SCAN: int = 500

    # Data import
    IMPORT_MAX_ROWS: int = 100_000

    # Telephony / voice
    TELEPHONY_PROVIDER: str = "mock"  # twilio | exotel | plivo | mock | simulation
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""
    EXOTEL_PHONE_NUMBER: str = ""
    PLIVO_AUTH_ID: str = ""
    PLIVO_AUTH_TOKEN: str = ""
    PLIVO_PHONE_NUMBER: str = ""
    VOICE_PUBLIC_URL: str = ""
    STT_PROVIDER: str = "mock"
    STT_API_KEY: str = ""
    STT_WHISPER_MODEL: str = "base"  # tiny | base | small | medium (free, local)
    STT_VOSK_MODEL_DIR: str = "voice_models"
    TTS_PROVIDER: str = "mock"
    TTS_API_KEY: str = ""
    TTS_EDGE_VOICE: str = ""  # optional override; defaults map by language
    VOICE_GREETING: str = (
        "Namaste. Welcome to IN-GRES AI, your groundwater information assistant. "
        "You can ask your question in English, Telugu, or Hindi."
    )
    VOICE_SILENCE_TIMEOUT_SECONDS: int = 8
    VOICE_MAX_SILENCE_PROMPTS: int = 2
    VOICE_RECORDING_ENABLED: bool = False

    # Backward-compatible aliases used by earlier phases
    TELEPHONY_ACCOUNT_ID: str = ""
    TELEPHONY_AUTH_TOKEN: str = ""
    TELEPHONY_PHONE_NUMBER: str = "+15005550000"

    SEED_ADMIN_EMAIL: str = "admin@ingres.in"
    SEED_ADMIN_PASSWORD: str = "admin12345"
    SEED_USER_EMAIL: str = "user@ingres.in"
    SEED_USER_PASSWORD: str = "user12345"

    # Demo dataset seeding: "national" (all-India synthetic, ~600k villages) |
    # "demo" (small 2-state sample used by tests) | "none"
    SEED_DATASET: str = "national"
    # 0 = auto-distribute to reach the national village target; set a positive
    # number to force the same village count per district (faster, for dev).
    SEED_VILLAGES_PER_DISTRICT: int = 0

    # Real (non-demo) CGWB/IMD data import. When true, `local_init` also loads
    # the station-level CSVs under STATES_DATA_DIR via app.ingres.real_import.
    SEED_REAL_DATA: bool = False
    # When true, the app refreshes the real dataset at every boot: CSVs are
    # fingerprinted and only states whose files changed are re-imported in
    # place, so live data stays current automatically.
    REAL_DATA_AUTO_REFRESH: bool = False
    # Directory of <state_name>.csv files produced by the PDF-extraction
    # pipeline (one file per state). Relative paths resolve against the repo.
    STATES_DATA_DIR: str = "states"

    # Live government data. When enabled, the app pulls fresh groundwater
    # levels from the CGWB telemetry dataset served by the National Water Data
    # Portal (open API, no key) and — when IMD_API_KEY is set — district
    # rainfall from the IMD API, on top of the CSV baseline.
    LIVE_DATA_ENABLED: bool = False
    # Period (minutes) for the background live-data sync loop.
    LIVE_SYNC_INTERVAL_MINUTES: int = 360
    # IMD API key + base URL (https://api.imd.gov.in). Requires registration
    # and IP whitelisting; when empty, IMD rainfall is skipped gracefully.
    IMD_API_KEY: str = ""
    IMD_API_BASE_URL: str = "https://api.imd.gov.in/api/v1"
    # Maximum distance (km) to match a live telemetry station to a village.
    LIVE_STATION_MATCH_RADIUS_KM: float = 15.0

    # Web Push (PWA) notifications. Keys are generated on first boot and stored
    # under DATA_DIR when not provided explicitly.
    WEB_PUSH_ENABLED: bool = False
    WEB_PUSH_EMAIL: str = "admin@ingres.in"
    WEB_PUSH_VAPID_PUBLIC_KEY: str = ""
    WEB_PUSH_VAPID_PRIVATE_KEY: str = ""
    DATA_DIR: str = "data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def data_dir(self) -> Path:
        p = Path(self.DATA_DIR)
        if p.is_absolute():
            return p
        for base in (Path.cwd(), _REPO_ROOT, _REPO_ROOT / "backend"):
            candidate = base / p
            if candidate.is_dir():
                return candidate
        return _REPO_ROOT / p

    @property
    def knowledge_dir(self) -> Path:
        """Resolve the knowledge directory to an absolute path."""
        p = Path(self.KNOWLEDGE_DIR)
        if p.is_absolute():
            return p
        for base in (Path.cwd(), _REPO_ROOT, _REPO_ROOT / "backend"):
            candidate = base / p
            if candidate.is_dir():
                return candidate
        return _REPO_ROOT / p

    @property
    def states_data_dir(self) -> Path:
        """Resolve the real-data state CSV directory to an absolute path."""
        p = Path(self.STATES_DATA_DIR)
        if p.is_absolute():
            return p
        for base in (Path.cwd(), _REPO_ROOT, _REPO_ROOT / "backend"):
            candidate = base / p
            if candidate.is_dir():
                return candidate
        return _REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()