"""
Cấu hình ứng dụng — đọc từ biến môi trường (file .env).
Xem .env.example để biết danh sách đầy đủ + giá trị mẫu.
"""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str | None = None
    postgres_user: str = "ketoan"
    postgres_password: str = "changeme_in_env_file"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "ketoan_db"

    @model_validator(mode="after")
    def _resolve_settings(self):
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        if not self.scan_extraction_provider:
            self.scan_extraction_provider = self.scan_provider
        return self

    # JWT auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"  # đổi giá trị này trong .env khi deploy thật
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12 tiếng

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 15

    # CORS - domain của Frontend khi deploy (VD: "https://ketoan.congty-cua-ban.com")
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Người dùng admin khởi tạo lần đầu (dùng bởi scripts/seed_initial_data.py)
    initial_admin_username: str = "admin"
    initial_admin_password: str = "CHANGE_ME_ON_FIRST_LOGIN"

    # Dùng cho tính năng scan bảng kê -> phiếu chi (app/services/scan_extraction_service.py)
    # --- Provider Claude (Anthropic) ---
    anthropic_api_key: str = ""
    scan_extraction_model: str = "claude-sonnet-4-6"

    # --- Provider NVIDIA NIM (OpenAI-compatible) ---
    nim_api_key: str = ""
    nim_extraction_model: str = "meta/llama-3.2-90b-vision-instruct"
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Chọn provider: "claude" (hoặc "anthropic") | "nim" | "ollama"
    scan_provider: str = "claude"
    scan_extraction_provider: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "gemma3:4b"

    # --- Agent-BE (app/agent/) — tách riêng khỏi SCAN_PROVIDER ---
    # "claude" | "nim" | "ollama". nim/ollama dùng chung NIM_API_KEY / OLLAMA_BASE_URL ở trên.
    # Model phải hỗ trợ tool-calling (chưa kiểm chứng thật với 2 model mặc định bên dưới).
    agent_provider: str = "claude"
    agent_nim_model: str = "meta/llama-3.3-70b-instruct"
    agent_ollama_model: str = "qwen2.5:7b"


settings = Settings()
